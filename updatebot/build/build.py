#
# Copyright (c) SAS Institute, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#


"""
Builder object implementation.
"""

import os
import xml
import stat
import time
import logging
import tempfile
import itertools

from conary import trove
from conary import files
from conary import rpmhelper
from conary import conarycfg
from conary.deps import deps
from conary import conaryclient
from conary.repository import changeset
from conary.repository.netrepos.proxy import ChangesetFilter

from rmake import plugins
from rmake.build import buildcfg
from rmake.cmdline import commit
from rmake.cmdline import helper
from rmake.cmdline import monitor

from updatebot.lib import util
from updatebot.conaryhelper import ConaryHelper
from updatebot.errors import JobFailedError
from updatebot.errors import CommitFailedError
from updatebot.errors import UnhandledKernelModule
from updatebot.errors import GroupBuildNotSupportedError
from updatebot.errors import InvalidBuildTroveInputError
from updatebot.errors import FailedToRetrieveChangesetError
from updatebot.errors import ChangesetValidationFailedError

from updatebot.build.cvc import Cvc
from updatebot.build.jobs import LocalDispatcher
from updatebot.build.jobs import OrderedCommitDispatcher
from updatebot.build.dispatcher import Dispatcher
from updatebot.build.dispatcher import RebuildDispatcher
from updatebot.build.dispatcher import PromoteDispatcher
from updatebot.build.dispatcher import NonCommittalDispatcher
from updatebot.build.callbacks import StatusOnlyDisplay

log = logging.getLogger('updatebot.build')

def jobInfoExceptionHandler(func):
    def deco(self, *args, **kwargs):
        retry = kwargs.pop('retry', 100)

        exception = None
        while retry:
            try:
                ret = func(self, *args, **kwargs)
                return ret
            except xml.parsers.expat.ExpatError, e:
                exception = None
            except Exception, e:
                if retry is True:
                    raise
                exception = e

            if type(retry) == int:
                retry -= 1

            # sleep between each retry
            time.sleep(5)

        if exception is not None:
            raise exception

    return deco


class Builder(object):
    """
    Class for wrapping the rMake api until we can switch to using rBuild.

    @param cfg: updateBot configuration object
    @type cfg: config.UpdateBotConfig
    @param ui: command line user interface.
    @type ui: cmdline.ui.UserInterface
    """

    def __init__(self, cfg, ui, rmakeCfgFn=None, conaryCfg=None, rmakeCfg=None):
        self._cfg = cfg
        self._ui = ui

        if conaryCfg:
            self._ccfg = conaryCfg
        else:
            self._ccfg = conarycfg.ConaryConfiguration(readConfigFiles=False)
            self._ccfg.read(util.join(self._cfg.configPath, 'conaryrc'))
            self._ccfg.dbPath = ':memory:'
            self._ccfg.initializeFlavors()

        self._client = conaryclient.ConaryClient(self._ccfg)

        if self._cfg.saveChangeSets or self._cfg.sanityCheckChangesets:
            self._saveChangeSets = tempfile.mkdtemp(
                prefix=self._cfg.platformName,
                suffix='-import-changesets')
        else:
            self._saveChangeSets = False

        self._sanityCheckChangesets = self._cfg.sanityCheckChangesets
        self._sanityCheckCommits = self._cfg.sanityCheckCommits

        if rmakeCfg:
            self._rmakeCfg = rmakeCfg
        else:
            self._rmakeCfg = self._getRmakeConfig(rmakeCfgFn=rmakeCfgFn)

        self._helper = helper.rMakeHelper(buildConfig=self._rmakeCfg)

        self.cvc = Cvc(self._cfg, self._ccfg, self._formatInput,
                       LocalDispatcher(self, 12))

        self._asyncDispatcher = OrderedCommitDispatcher(self, 30)

        self._conaryhelper = ConaryHelper(self._cfg)

    def _getRmakeConfig(self, rmakeCfgFn=None):
        # Get default pluginDirs from the rmake cfg object, setup the plugin
        # manager, then create a new rmake config object so that rmakeUser
        # will be parsed correctly.
        rmakeCfg = buildcfg.BuildConfiguration(readConfigFiles=False)
        disabledPlugins = [ x[0] for x in rmakeCfg.usePlugin.items()
                            if not x[1] ]
        disabledPlugins.append('monitor')
        pluginMgr = plugins.PluginManager(rmakeCfg.pluginDirs, disabledPlugins)
        pluginMgr.loadPlugins()
        pluginMgr.callClientHook('client_preInit', self, [])

        rmakerc = 'rmakerc'
        if rmakeCfgFn:
            rmakeCfgPath = util.join(self._cfg.configPath, rmakeCfgFn)
            if os.path.exists(rmakeCfgPath):
                rmakerc = rmakeCfgFn
                # FIXME: This is a hack to work around having two conaryrc
                #        files, one for building groups and one for building
                #        packages.
                self._ccfg.autoLoadRecipes = []
            else:
                log.warn('%s not found, falling back to rmakerc' % rmakeCfgFn)

        rmakeCfg = buildcfg.BuildConfiguration(readConfigFiles=False)
        rmakeCfg.read(util.join(self._cfg.configPath, rmakerc))
        rmakeCfg.useConaryConfig(self._ccfg)
        rmakeCfg.copyInConfig = False
        rmakeCfg.strictMode = True

        # Use default tmpDir when building with rMake since the specified
        # tmpDir may not exist in the build root.

        rmakeCfg.resetToDefault('tmpDir')

        return rmakeCfg

        self._conaryhelper = ConaryHelper(self._cfg)

    def build(self, troveSpecs):
        """
        Build a list of troves.
        @param troveSpecs: list of trove specs
        @type troveSpecs: [(name, versionObj, flavorObj), ...]
        @return troveMap: dictionary of troveSpecs to built troves
        """

        if not troveSpecs:
            return {}

        troves = self._formatInput(troveSpecs)
        jobId = self._startJob(troves)
        self._monitorJob(jobId, retry=2)
        self._sanityCheckJob(jobId)
        trvMap = self._commitJob(jobId)
        ret = self._formatOutput(trvMap)
        return ret

    def buildmany(self, troveSpecs, lateCommit=False, workers=None,
            retries=None):
        """
        Build many troves in separate jobs.
        @param troveSpecs: list of trove specs
        @type troveSpecs: [(name, versionObj, flavorObj), ...]
        @param lateCommit: if True, build all troves, then commit. (defaults to
                           False)
        @type lateCommit: boolean
        @return troveMap: dictionary of troveSpecs to built troves
        """

        if not workers:
            workers = 30

        if not retries:
            retries = 0


        if self._cfg.updateMode == 'current':
            if self._cfg.targetLabel == self._cfg.sourceLabel[-1]:
                dispatcher = Dispatcher(self, workers, retries=retries)
            else:
                dispatcher = PromoteDispatcher(self, workers, retries=retries)
        elif not lateCommit:
            dispatcher = Dispatcher(self, workers, retries=retries)
        else:
            dispatcher = NonCommittalDispatcher(self, workers, retries=retries)
        return dispatcher.buildmany(troveSpecs)

    def buildsplitarch(self, troveSpecs):
        """
        Build a list of packages, in N jobs where N is the number of
        configured arch contexts.
        @param troveSpecs: list of trove specs
        @type troveSpecs: [(name, versionObj, flavorObj), ...]
        @return troveMap: dictionary of troveSpecs to built troves
        """

        if not troveSpecs:
            return {}

        # Split troves by context.
        jobs = {}
        for trv in self._formatInput(troveSpecs):
            if len(trv) != 4:
                continue

            key = trv[3]
            if key not in jobs:
                jobs[key] = []
            jobs[key].append(trv)

        # Start all build jobs.
        jobIds = {}
        for ctx, job in jobs.iteritems():
            jobIds[ctx] = self._startJob(job)

        fmtstr = ', '.join([ '%s:%s' % (x, y) for x, y in jobIds.iteritems()])
        log.info('Started %s' % fmtstr)

        # Wait for the jobs to finish.
        log.info('Waiting for jobs to complete')
        for jobId in jobIds.itervalues():
            self._monitorJob(jobId)

        # Sanity check all jobs.
        for jobId in jobIds.itervalues():
            self._sanityCheckJob(jobId)

        # Commit if all jobs were successfull.
        trvMap = self._commitJob(jobIds.values())

        ret = self._formatOutput(trvMap)
        return ret

    def buildasync(self, troveSpec):
        """
        Build troves in much the same way buildmany does, but without blocking
        the main thread.
        @param troveSpec: name, version, flavor tuple
        @type troveSpec: tuple(str, conary.versions.VersionFromString, None)
        @return status object
        @rtype updatebot.build.jobs.Status
        """

        return self._asyncDispatcher.build(troveSpec)

    def rebuild(self, troveSpecs, useLatest=None, additionalResolveTroves=None,
        commit=True):
        """
        Rebuild a set of troves in the same environment that they were
        orignally built in.
        @param troveSpecs: set of name, version, flavor tuples
        @type troveSpecs: set([(name, version, flavor), ..])
        @param useLatest: A list of package names to use the latest versions of.
                          For instance, you may want to use the latest version
                          of conary to get fixed dependencies.
        @type useLatest: list(str, ...)
        @param additionalResolveTroves: List of additional trove specs to add to
                                        the resolve troves.
        @type additionalResolveTroves: list(str, ...)
        @param commit: Controls waiting for jobs to complete and then committing
                       them one at a time. (default: True)
        @type commit: boolean
        @return if commit: troveMap: dictionary of troveSpecs to built troves
        @return if not commit: list of jobIds
        """

        # Set some defaults
        if useLatest is None:
            useLatest = []
        if additionalResolveTroves is None:
            additionalResolveTroves = []

        def grpByNameVersion(jobLst):
            lst = {}
            for job in jobLst:
                lst.setdefault(tuple(job[:2]), set()).add(job)

            return [ lst[x] for x in sorted(lst.keys()) ]

        def startOne(job):
            # Get a new builder so that we don't change the configuration of the
            # existing builder.
            cls = self.__class__
            builder = cls(self._cfg, self._ui)

            # Find the troves that were originally used to build the requested
            # trove.
            n, v = list(job)[0][:2]
            # So that we can find the latest binary built from the closest
            # versioned source we need to lookup binary versions and then use
            # that source to get the rest of the binaries. We need to do this
            # in the case that we are building a source that has been modified
            # to remove a recipe or something like that.
            upVer = '/'.join([v.branch().label().asString(),
                              v.trailingRevision().version])
            binSpecs = self._client.repos.findTrove(v.branch().label(),
                                                    (n, upVer, None))
            binTrv = self._client.repos.getTrove(*binSpecs[0], withFiles=False)
            srcName = binTrv.troveInfo.sourceName()
            srcVersion = binTrv.getVersion().getSourceVersion()

            specs = self._client.repos.getTrovesBySource(srcName, srcVersion)

            # Find the latest version of each package
            vMap = {}
            for n, v, f in specs:
                n = n.split(':')[0]
                vMap.setdefault(v, dict()).setdefault(n, set()).add(f)

            latest = sorted(vMap)[-1]
            trvSpecs = []
            for n, flvs in vMap[latest].iteritems():
                for f in flvs:
                    trvSpecs.append((n, latest, f))

            # Get the troves for all binaries built from the given source.
            troves = self._client.repos.getTroves(trvSpecs, withFiles=False)

            # Take the union of all buildreqs for all flavors of the package.
            reqs = set()
            for trv in troves:
                for req in trv.troveInfo.buildReqs.iter():
                    name = req.name()
                    version = req.version()
                    if useLatest and name.split(':')[0] in useLatest:
                        # XXX - this broke for me at some point, so I
                        # switched to using "continue" here; I've now
                        # forgotten the reason, and so changed it back. - AG
                        version = version.branch()
                    reqs.add((name, version))

            # Reconfigure builder to use previous buildrequires as
            # resolveTroves.
            resolveTroves = ' '.join([ '%s=%s' % x for x in reqs ])

            # Add any additional resolve troves.
            resolveTroves += ' ' + ' '.join(additionalResolveTroves)

            builder._rmakeCfg.resolveTroves = []
            builder._rmakeCfg.configLine('resolveTroves %s' % resolveTroves)

            # Start the job.
            jobId = builder._startJob(job)

            return jobId


        # Handle empty set.
        if not troveSpecs:
            return {}

        jobs = self._formatInput(troveSpecs)

        # Sanity check input to make sure there are no groups.
        if [ x for x in jobs if x[0].startswith('group-') ]:
            raise GroupBuildNotSupportedError

        # Start all of the jobs.
        jobIds = []
        for job in grpByNameVersion(jobs):
            jobIds.append(startOne(job))

        # If not committing jobs, return the list of ids.
        if not commit:
            return jobIds

        # Wait for jobs to complete
        dispatcher = NonCommittalDispatcher(self, 0)
        dispatcher.watchmany(jobIds)

        # Commit jobs in order, conary does not do this for you.
        trvMap = {}
        for jobId in jobIds:
            trvMap.update(self._commitJob(jobId))
        ret = self._formatOutput(trvMap)

        return ret

    def rebuildmany(self, troveSpecs, useLatest=None,
        additionalResolveTroves=None, commit=True):
        """
        Rebuild a set of troves in the same environment that they were
        orignally built in.
        @param troveSpecs: set of name, version, flavor tuples
        @type troveSpecs: set([(name, version, flavor), ..])
        @param useLatest: A list of package names to use the latest versions of.
                          For instance, you may want to use the latest version
                          of conary to get fixed dependencies.
        @type useLatest: list(str, ...)
        @param additionalResolveTroves: List of additional trove specs to add to
                                        the resolve troves.
        @type additionalResolveTroves: list(str, ...)
        @param commit: Controls waiting for jobs to complete and then committing
                       them one at a time. (default: True)
        @type commit: boolean
        @return if commit: troveMap: dictionary of troveSpecs to built troves
        @return if not commit: list of jobIds
        """

        dispatcher = RebuildDispatcher(self, 30, useLatest=useLatest,
            additionalResolveTroves=additionalResolveTroves)

        return dispatcher.buildmany(troveSpecs)


    def start(self, troveSpecs):
        """
        Public version of start job that starts a job without monitoring.
        @param troveSpecs: set of name, version, flavor tuples
        @type troveSpecs: set([(name, version, flavor), ..])
        @return jobId: integer
        """

        troves = self._formatInput(troveSpecs)
        jobId = self._startJob(troves)
        return jobId

    def watch(self, jobId):
        """
        Watch a build.
        @param jobId: rMake job ID
        @type jobId: integer
        """

        self._monitorJob(jobId)

    def commit(self, jobId):
        """
        Public commit from jobId with sanity checking.
        @param jobId: id of the build job to commit
        @type jobId: integer
        @return dict((name, version, flavor)=
                     set([(name, version, flavor), ...])
        """

        self._sanityCheckJob(jobId)
        trvMap = self._commitJob(jobId)
        ret = self._formatOutput(trvMap)
        return ret

    def orderJobs(self, troveSpecs):
        """
        Create a sorted list of troveSpecs, grouped according to the config.
        @param troveSpecs: list of source name, source version, and flavor.
        @type troveSpecs: iterable of three tuples
        """

        order = []

        bucketMap = {}
        for grouping in self._cfg.combinePackages:
            for pkg in grouping:
                bucketMap[pkg] = self._cfg.combinePackages.index(grouping)

        buckets = {}
        for nvf in sorted(troveSpecs):
            name = nvf[0]
            if name in bucketMap:
                if name not in buckets:
                    order.append([])
                    idx = len(order) - 1

                    for pkg in self._cfg.combinePackages[bucketMap[name]]:
                        buckets[name] = idx

                idx = buckets[name]
                order[idx].append(nvf)
            else:
                order.append(nvf)

        return order

    def setCommitFailed(self, jobId, reason=None):
        """
        Sets the job as failed in rmake.
        @param jobId: id of the build job to commit
        @type jobId: integer
        @param reason: message to be stored on the rmake server
        @type resaon: str
        """

        reason = reason and reason or 'none specified'
        self._helper.client.commitFailed([jobId, ], reason)

    def _formatInput(self, troveSpecs):
        """
        Formats the list of troves provided into a job list for rMake.
        @param troveSpecs: set of name, version, flavor tuples
        @type troveSpecs: set([(name, version, flavor, optional list of binary
                                names), ..])
        @return list((name, version, flavor, context), ...)
        """

        # Make sure troveSpecs is an iterable of three tuples.
        if (len(troveSpecs) in (3, 4) and
            not isinstance(list(troveSpecs)[0], (list, set, tuple))):
            # Assume that (n,v,f) was passed in
            troveSpecs = [ troveSpecs, ]

        # Build all troves in defined contexts.
        troves = []
        for trv in troveSpecs:
            if len(trv) == 3:
                name, version, flavor = trv
                binaryNames = None
            elif len(trv) == 4:
                name, version, flavor, binaryNames = trv
            else:
                raise InvalidBuildTroveInputError(input=trv)

            # Make sure name is not an unicode string, it causes breakage in
            # the deps modules in conary.
            name = name.encode()

            # Make sure name is not a component, like a source component.
            name = name.split(':')[0]

            # Build groups in all of the defined flavors. We don't need a
            # context here since groups are all built in a single job.
            if name.startswith('group-'):
                for flv in self._cfg.groupFlavors:
                    troves.append((name, version, flv))

            # Handle special package flavors when specified.
            elif name in self._cfg.packageFlavors:
                for context, flavor in self._cfg.packageFlavors[name]:
                    troves.append((name, version, flavor, context))

            # Kernels are special.
            elif ((name == 'kernel' or
                   name in self._cfg.kernelModules or
                   util.isKernelModulePackage(name))
                  and self._cfg.kernelFlavors):
                for context, flavor in self._cfg.kernelFlavors:
                    # Replace flag name to match package
                    if name != 'kernel':
                        flavor = deps.parseFlavor(
                            str(flavor).replace('kernel', name))
                    troves.append((name, version, flavor, context))

            # Check if this looks like a kernel module source rpm that wasn't
            # handled by the last two checks.
            elif '-kmod' in name or '-kmp' in name:
                log.error('raising error for kernel module package %s' % name)
                raise UnhandledKernelModule(name=name)

            # All other packages.
            else:
                # Build all packages as x86 and x86_64.
                for context, fltr in self._cfg.archContexts:
                    # If this is no filter or if there is a filter and a binary
                    # package matches the filter build in this context.
                    if (not fltr or (fltr and
                            [ x for x in binaryNames if fltr[1].match(x) ])):
                        troves.append((name, version, flavor, context))

            # Handle any special-case omissions
            # (e.g. due to missing packages)
            if name in self._cfg.packageFlavorsMissing:
                for context, flavor, fltr in self._cfg.packageFlavorsMissing[name]:
                    if not [ x for x in binaryNames if fltr[1].match(x) ]:
                        troves.remove((name, version, flavor, context))

            assert troves

        return sorted(set(troves))

    @jobInfoExceptionHandler
    def _getJob(self, jobId, retry=None):
        """
        Get a job instance from the rMake helper, catching several common
        exceptions.
        @param jobId: id of an rMake job
        @type jobId: integer
        @param retry: information about retrying the get job, if retry is None
                      then retry forever, if retry is an integer retry n times.
        @type retry: None
        @type retry: integer
        @return rmake job instance
        """

        if not isinstance(jobId, (list, tuple, set)):
            return self._helper.client.getJob(jobId)
        else:
            return self._helper.client.getJobs(jobId)

    def _startJob(self, troveSpecs):
        """
        Create and start a rMake build.
        @param troveSpecs: list of trove specs
        @type troveSpecs: [(name, versionObj, flavorObj), ...]
        @return integer jobId
        """

        # Create rMake job
        log.info('Creating build job: %s' % (troveSpecs, ))
        job = self._helper.createBuildJob(list(troveSpecs))
        jobId = self._helper.buildJob(job)
        log.info('Started jobId: %s' % jobId)

        return jobId

    @jobInfoExceptionHandler
    def _monitorJob(self, jobId):
        """
        Monitor job status, block until complete.
        @param jobId: rMake job ID
        @type jobId: integer
        """

        # Watch build, wait for completion
        monitor.monitorJob(self._helper.client, jobId,
            exitOnFinish=True, displayClass=StatusOnlyDisplay)

    def _sanityCheckJob(self, jobIds):
        """
        Verify the status of a job.
        @param jobIds: rMake job ID, or list of jobIds
        @type jobIds: integer or iterable
        """

        if not isinstance(jobIds, (tuple, list, set)):
            jobIds = [ jobIds, ]

        # Check for errors
        for job in self._getJob(jobIds):
            jobId = job.jobId
            if job.isFailed():
                log.error('Job %d failed', jobId)
                raise JobFailedError(jobId=jobId, why=job.status)
            elif not job.isFinished():
                log.error('Job %d is not done, yet watch returned early!',
                          jobId)
                raise JobFailedError(jobId=jobId, why=job.status)
            elif not list(job.iterBuiltTroves()):
                log.error('Job %d has no built troves', jobId)
                raise JobFailedError(jobId=jobId, why='No troves found in job')

    def _sanityCheckRPMCapsule(self, jobId, fileList, fileObjs, rpmFile):
        """
        Compare an rpm capsule with the contents of a
        trove to make sure that they agree.
        """

        rpmFile.seek(0)
        h = rpmhelper.readHeader(rpmFile, checkSize=False)
        rpmFileList = dict(
            itertools.izip(h[rpmhelper.OLDFILENAMES],
                           itertools.izip(h[rpmhelper.FILEUSERNAME],
                                          h[rpmhelper.FILEGROUPNAME],
                                          h[rpmhelper.FILEMODES],
                                          h[rpmhelper.FILESIZES],
                                          h[rpmhelper.FILERDEVS],
                                          h[rpmhelper.FILEFLAGS],
                                          h[rpmhelper.FILEVERIFYFLAGS],
                                          h[rpmhelper.FILELINKTOS],
                                          )))

        errors = []

        foundFiles = dict.fromkeys(rpmFileList)

        def fassert(test, path='', why=''):
            if not test:
                errors.append((path, why))

        def devassert(path, rDev, fileObj):
            minor = rDev & 0xff | (rDev >> 12) & 0xffffff00
            major = (rDev >> 8) & 0xfff
            fassert(fileObj.devt.major() == major, path,
                    'Device major mismatch: RPM %d != Conary %d'
                    %(major, fileObj.devt.major()))
            fassert(fileObj.devt.minor() == minor, path,
                    'Device minor mismatch: RPM %d != Conary %d'
                    %(minor, fileObj.devt.minor()))
            fassert(not fileObj.flags.isPayload(), path,
                    'Device file is marked as payload')

        for fileInfo, fileObj in zip(fileList, fileObjs):
            fpath = fileInfo[1]
            foundFiles[fpath] = True
            rUser, rGroup, rMode, rSize, rDev, rFlags, rVflags, rLinkto = \
                rpmFileList[fpath]

            # First, tests based on the Conary changeset

            # file metadata verification
            if (rUser != fileObj.inode.owner() or
                rGroup != fileObj.inode.group()):
                fassert(False, fpath,
                        'User/Group mismatch: RPM %s:%s != Conary %s:%s'
                        %(rUser, rGroup,
                          fileObj.inode.owner(), fileObj.inode.group()))

            if isinstance(fileObj, files.SymbolicLink):
                expectedMode = 0777 # CNY-3304
            else:
                expectedMode = stat.S_IMODE(rMode)
            if fileObj.inode.perms() != expectedMode:
                fassert(False, fpath,
                        'Mode mismatch: RPM 0%o != Conary 0%o'
                        %(expectedMode, fileObj.inode.perms()))

            if isinstance(fileObj, files.RegularFile):
                if not stat.S_ISREG(rMode):
                    fassert(False, fpath,
                            'Conary Regular file has non-regular mode 0%o'
                            %rMode)

                # RPM config flag mapping
                if rFlags & rpmhelper.RPMFILE_CONFIG:
                    if fileObj.linkGroup() or not fileObj.contents.size():
                        fassert(fileObj.flags.isInitialContents(), fpath,
                                'RPM config file without size or'
                                ' hardlinked is not InitialContents')
                    else:
                        fassert(fileObj.flags.isConfig() or
                                fileObj.flags.isInitialContents(), fpath,
                                'RPM config file is neither Config file '
                                'nor InitialContents')

            elif isinstance(fileObj, files.Directory):
                fassert(stat.S_ISDIR(rMode), fpath,
                        'Conary directory has non-directory RPM mode 0%o'
                        %rMode)
                fassert(not fileObj.flags.isPayload(), fpath,
                        'Conary directory marked as payload')

            elif isinstance(fileObj, files.CharacterDevice):
                fassert(stat.S_ISCHR(rMode), fpath,
                        'Conary CharacterDevice has RPM non-character-device'
                        ' mode 0%o' %rMode)
                devassert(fpath, rDev, fileObj)

            elif isinstance(fileObj, files.BlockDevice):
                fassert(stat.S_ISBLK(rMode), fpath,
                        'Conary BlockDevice has RPM non-block-device'
                        ' mode 0%o' %rMode)
                devassert(fpath, rDev, fileObj)

            elif isinstance(fileObj, files.NamedPipe):
                fassert(stat.S_ISFIFO(rMode), fpath,
                        'Conary NamedPipe has RPM non-named-pipe'
                        ' mode 0%o' %rMode)
                fassert(not fileObj.flags.isPayload(), fpath,
                        'NamedPipe file is marked as payload')

            elif isinstance(fileObj, files.SymbolicLink):
                fassert(stat.S_ISLNK(rMode), fpath,
                        'Conary SymbolicLink has RPM non-symlink'
                        ' mode 0%o' %rMode)
                fassert(fileObj.target() == rLinkto, fpath,
                        'Symlink target mismatch:'
                        ' RPM %s != Conary %s'
                        %(rLinkto, fileObj.target()))
                fassert(not fileObj.flags.isPayload(), fpath,
                        'SymbolicLink file is marked as payload')

            else:
                # unhandled file type
                fassert(False, fpath,
                        'Unknown Conary file type %r' %fileObj)

            # Now, some tests based on the contents of the RPM header
            if not stat.S_ISDIR(rMode) and rFlags & rpmhelper.RPMFILE_GHOST:
                fassert(fileObj.flags.isInitialContents(), fpath,
                        'RPM ghost non-directory is not InitialContents')

            if rFlags & rpmhelper.RPMFILE_MISSINGOK:
                fassert(fileObj.flags.isMissingOkay(), fpath,
                        'RPM missingok file does not have missingOkay flag')
            if fileObj.flags.isMissingOkay():
                fassert(rFlags & rpmhelper.RPMFILE_MISSINGOK, fpath,
                        'missingOkay file does not have RPM missingok flag')

            if not rVflags:
                # %doc -- CNY-3254
                fassert(not fileObj.flags.isInitialContents(), fpath,
                        'RPM %%doc file is InitialContents')

        # Make sure we have explicitly checked every file in the RPM
        uncheckedFiles = [x[0] for x in foundFiles.iteritems() if not x[1] ]
        fassert(not uncheckedFiles, str(uncheckedFiles),
                'Files contained in RPM not contained in Conary changeset')

        if errors:
            raise ChangesetValidationFailedError(jobId=jobId,
                    reason='\n'.join([
                        '%s: %s' %(x, y) for x, y in errors
                    ]))

    def _sanityCheckChangeSet(self, csFile, jobId):
        """
        Sanity check changeset before commit.
        """

        def idCmp(a, b):
            apid, afid = a[0][0], a[0][2]
            bpid, bfid = b[0][0], b[0][2]

            return cmp((apid, afid), (bpid, bfid))

        newCs = changeset.ChangeSetFromFile(csFile)
        log.info('[%s] comparing changeset to rpm capsules' % jobId)

        capsules = []
        for newTroveCs in newCs.iterNewTroveList():
            if newTroveCs.getTroveInfo().capsule.type() == 'rpm':
                if newTroveCs.getOldVersion():
                    name, version, flavor = newTroveCs.getOldNameVersionFlavor()
                    oldCsJob = [ (name, (None, None),
                                        (version, flavor), True) ]

                    oldCs = self._client.repos.createChangeSet(oldCsJob,
                        withFiles=True, withFileContents=False)

                    oldTroveCs = oldCs.getNewTroveVersion(
                        *newTroveCs.getOldNameVersionFlavor())
                    assert (oldTroveCs.getNewNameVersionFlavor() ==
                            newTroveCs.getOldNameVersionFlavor())
                    oldTrove = trove.Trove(oldTroveCs)
                    newTrove = oldTrove.copy()
                    newTrove.applyChangeSet(newTroveCs)

                else:
                    oldCs = None
                    oldTrove = None
                    newTrove = trove.Trove(newTroveCs)

                fileObjs = []
                # get file streams for comparison
                fileList = list(newTrove.iterFileList(capsules=False))
                for pathId, path, fileId, fileVer in fileList:
                    fileObjs.append(ChangesetFilter._getFileObject(
                        pathId, fileId, oldTrove, oldCs, newCs))

                capFileList = [ x for x in
                    newTrove.iterFileList(capsules=True) ]

                if len(capFileList) != 1:
                    raise FailedToRetrieveChangesetError(jobId=jobId, why='More'
                        ' than 1 RPM capsule in trove %s' % newTroveCs.name())

                capsules.append((capFileList[0], fileList, fileObjs))

        contentsCache = {}
        for capFile, fileList, fileObjs in sorted(capsules, cmp=idCmp):
            if capFile[2] in contentsCache:
                capsuleFileContents = contentsCache[capFile[2]]
            else:
                try:
                    getFileContents = newCs.getFileContents
                    fcList = getFileContents(capFile[0], capFile[2],
                                             compressed=False)
                    capsuleFileContents = fcList[1].get()
                except KeyError, e:
                    getFileContents = self._client.repos.getFileContents
                    fcList = getFileContents((capFile[2:], ), compressed=False)
                    capsuleFileContents = fcList[0].get()
                contentsCache[capFile[2]] = capsuleFileContents

            # do the check
            self._sanityCheckRPMCapsule(jobId, fileList, fileObjs,
                                        capsuleFileContents)

        # Make sure the changeset gets closed so that we don't run out of
        # file descriptors.
        del newCs

    def _commitJob(self, jobId):
        """
        Commit completed job.
        @param jobId: rMake job ID
        @type jobId: integer
        @return troveMap: dictionary of troveSpecs to built troves
        """

        if not isinstance(jobId, (list, tuple, set)):
            jobIds = [ jobId, ]
        else:
            jobIds = jobId

        jobIdsStr = ','.join(map(str, jobIds))

        # Do the commit
        startTime = time.time()
        jobs = self._getJob(jobIds)
        log.info('[%s] starting commit' % jobIdsStr)

        if self._saveChangeSets:
            csfn = tempfile.mktemp(dir=self._saveChangeSets, suffix='.ccs')

        writeToFile = self._saveChangeSets and csfn or None

        self._helper.client.startCommit(jobIds)
        succeeded, data = commit.commitJobs(
            self._helper.getConaryClient(),
            jobs,
            self._rmakeCfg.reposName,
            self._cfg.commitMessage,
            commitOutdatedSources=self._cfg.commitOutdatedSources,
            writeToFile=writeToFile)

        if not succeeded:
            self._helper.client.commitFailed(jobIds, data)
            raise CommitFailedError(jobId=jobIdsStr, why=data)

        if writeToFile:
            log.info('[%s] changeset saved to %s' % (jobIdsStr, writeToFile))

            if self._sanityCheckChangesets:
                self._sanityCheckChangeSet(writeToFile, jobIdsStr)

            log.info('[%s] committing changeset to repository' % jobIdsStr)
            self._client.repos.commitChangeSetFile(writeToFile)

        if self._sanityCheckCommits:
            # sanity check repository
            log.info('[%s] checking repository for sanity' % jobIdsStr)
            jobList = []
            for job in data.itervalues():
                for arch in job.itervalues():
                    for n, v, f in arch:
                        if n.startswith('group-'): continue
                        jobList.append((n, (None, None), (v, f), True))

            cs = self._client.repos.createChangeSet(jobList, withFiles=True,
                                                    withFileContents=False)

        log.info('[%s] commit completed in %.02f seconds',
                 jobIdsStr, time.time() - startTime)

        self._helper.client.commitSucceeded(data)

        troveMap = {}
        for troveTupleDict in data.itervalues():
            for buildTroveTuple, committedList in troveTupleDict.iteritems():
                troveMap[buildTroveTuple] = committedList

        return troveMap

    @staticmethod
    def _formatOutput(trvMap):
        """
        Format the output from rMake into something keyd off of the original
        input.
        @param trvMap: dictionary mapping of source to binary
        @type trvMap: dict((name, version, flavor, context)=
                            set([(name, version, flavor), ...]))
        @return dict((name, version, flavor)=
                     set([(name, version, flavor), ...])
        """

        # {(name, version, None): set([(name, version, flavor), ...])}
        ret = {}
        for sn, sv, sf, c in trvMap.iterkeys():
            n = sn.split(':')[0]
            if (n, sv, None) not in ret:
                ret[(n, sv, None)] = set()
            ret[(n, sv, None)].update(set(trvMap[(sn, sv, sf, c)]))

        return ret

    def _registerCommand(self, *args, **kwargs):
        """
        Fake rMake hook
        """
