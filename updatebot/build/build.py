#
# Copyright (c) 2008-2009 rPath, Inc.
#
# This program is distributed under the terms of the Common Public License,
# version 1.0. A copy of this license should have been distributed with this
# source file in a file called LICENSE. If it is not present, the license
# is always available at http://www.rpath.com/permanent/licenses/CPL-1.0.
#
# This program is distributed in the hope that it will be useful, but
# without any warranty; without even the implied warranty of merchantability
# or fitness for a particular purpose. See the Common Public License for
# full details.
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
from updatebot.errors import JobFailedError
from updatebot.errors import CommitFailedError
from updatebot.errors import FailedToRetrieveChangesetError
from updatebot.errors import ChangesetValidationFailedError

from updatebot.build.dispatcher import Dispatcher
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
    """

    def __init__(self, cfg, rmakeCfgFn=None):
        self._cfg = cfg

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

        self._rmakeCfg = buildcfg.BuildConfiguration(readConfigFiles=False)
        self._rmakeCfg.read(util.join(self._cfg.configPath, rmakerc))
        self._rmakeCfg.useConaryConfig(self._ccfg)
        self._rmakeCfg.copyInConfig = False
        self._rmakeCfg.strictMode = True

        # Use default tmpDir when building with rMake since the specified
        # tmpDir may not exist in the build root.
        self._rmakeCfg.tmpDir = conarycfg.ConaryContext.tmpDir[1]

        self._helper = helper.rMakeHelper(buildConfig=self._rmakeCfg)

    def build(self, troveSpecs):
        """
        Build a list of troves.
        @param troveSpecs: list of trove specs
        @type troveSpecs: [(name, versionObj, flavorObj), ...]
        @return troveMap: dictionary of troveSpecs to built troves
        """

        troves = self._formatInput(troveSpecs)
        jobId = self._startJob(troves)
        self._monitorJob(jobId, retry=2)
        self._sanityCheckJob(jobId)
        trvMap = self._commitJob(jobId)
        ret = self._formatOutput(trvMap)
        return ret

    def buildmany(self, troveSpecs):
        """
        Build many troves in separate jobs.
        @param troveSpecs: list of trove specs
        @type troveSpecs: [(name, versionObj, flavorObj), ...]
        @return troveMap: dictionary of troveSpecs to built troves
        """

        dispatcher = Dispatcher(self, 30)
        return dispatcher.buildmany(troveSpecs)

    def buildsplitarch(self, troveSpecs):
        """
        Build a list of packages, in N jobs where N is the number of
        configured arch contexts.
        @param troveSpecs: list of trove specs
        @type troveSpecs: [(name, versionObj, flavorObj), ...]
        @return troveMap: dictionary of troveSpecs to built troves
        """

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
        @type troveSpecs: set([(name, version, flavor), ..])
        @return list((name, version, flavor, context), ...)
        """

        # Build all troves in defined contexts.
        troves = []
        for name, version, flavor in troveSpecs:
            # Make sure name is not an unicode string, it causes breakage in
            # the deps modules in conary.
            name = name.encode()

            # Build groups in all of the defined falvors. We don't need a
            # context here since groups are all built in a single job.
            if name.startswith('group-'):
                for flv in self._cfg.groupFlavors:
                    troves.append((name, version, flv))

            # Kernels are special.
            elif ((name == 'kernel' or
                   name in self._cfg.kernelModules or
                   util.isKernelModulePackage(name))
                  and self._cfg.kernelFlavors):
                for context, flavor in self._cfg.kernelFlavors:
                    # Replace flag name to match package
                    if name != 'kernel':
                        # Don't build kernel modules with a .debug flag, that
                        # is only for kernels.
                        if flavor.stronglySatisfies(
                            deps.parseFlavor('kernel.debug')):
                            continue
                        flavor = deps.parseFlavor(
                            str(flavor).replace('kernel', name))
                    troves.append((name, version, flavor, context))

            # Handle special package flavors when specified.
            elif name in self._cfg.packageFlavors:
                for context, flavor in self._cfg.packageFlavors[name]:
                    troves.append((name, version, flavor, context))

            # All other packages.
            else:
                # Build all packages as x86 and x86_64.
                for context in self._cfg.archContexts:
                    troves.append((name, version, flavor, context))

        return troves

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
        job = self._helper.createBuildJob(troveSpecs)
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

            if stat.S_IMODE(rMode) != fileObj.inode.perms():
                fassert(False, fpath,
                        'Mode mismatch: RPM 0%o != Conary 0%o'
                        %(rMode, fileObj.inode.perms()))

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
            elif newTroveCs.getOldVersion():
                getFileContents = self._client.repos.getFileContents
                fcList = getFileContents((capFile[2:], ), compressed=False)
                capsuleFileContents = fcList[0].get()
            else:
                getFileContents = newCs.getFileContents
                fcList = getFileContents(capFile[0], capFile[2],
                                         compressed=False)
                capsuleFileContents = fcList[1].get()
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
        succeeded, data = commit.commitJobs(self._helper.getConaryClient(),
                                            jobs,
                                            self._rmakeCfg.reposName,
                                            self._cfg.commitMessage,
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
