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

import time
import logging
import tempfile

import xml
from Queue import Queue, Empty
from threading import Thread, RLock

from conary.deps import deps
from conary import conarycfg, conaryclient

from rmake import plugins
from rmake.build import buildcfg
from rmake.cmdline import helper, monitor, commit

from updatebot.lib import util
from updatebot import subscriber
from updatebot.errors import JobFailedError, CommitFailedError

log = logging.getLogger('updateBot.build')

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
    @param saveChangeSets: directory to save changesets to
    @type saveChangeSets: str
    """

    def __init__(self, cfg, rmakeCfgFn=None, saveChangeSets=None):
        self._cfg = cfg

        self._ccfg = conarycfg.ConaryConfiguration(readConfigFiles=False)
        self._ccfg.read(util.join(self._cfg.configPath, 'conaryrc'))
        self._ccfg.dbPath = ':memory:'
        self._ccfg.initializeFlavors()

        self._client = conaryclient.ConaryClient(self._ccfg)

        if saveChangeSets is None and self._cfg.saveChangeSets:
            self._saveChangeSets = tempfile.mkdtemp(
                prefix=self._cfg.platformName,
                suffix='-import-changesets')
        else:
            self._saveChangeSets = saveChangeSets

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

        dispatcher = subscriber.Dispatcher(self, 30)
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

            # Don't set context for groups, they will already have the
            # correct flavors.
            if name.startswith('group-'):
                troves.append((name, version, flavor))

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
                        if flavor.stronglySatisfies(deps.parseFlavor('kernel.debug')):
                            continue
                        flavor = deps.parseFlavor(str(flavor).replace('kernel', name))
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
        @type retry: integet
        @return rmake job instance
        """

        return self._helper.getJob(jobId)

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
            exitOnFinish=True, displayClass=_StatusOnlyDisplay)

    def _sanityCheckJob(self, jobId):
        """
        Verify the status of a job.
        @param jobId: rMake job ID
        @type jobId: integer
        """

        # Check for errors
        job = self._getJob(jobId)
        if job.isFailed():
            log.error('Job %d failed', jobId)
            raise JobFailedError(jobId=jobId, why=job.status)
        elif not job.isFinished():
            log.error('Job %d is not done, yet watch returned early!', jobId)
            raise JobFailedError(jobId=jobId, why=job.status)
        elif not list(job.iterBuiltTroves()):
            log.error('Job %d has no built troves', jobId)
            raise JobFailedError(jobId=jobId, why='No troves found in job')

    def _commitJob(self, jobId):
        """
        Commit completed job.
        @param jobId: rMake job ID
        @type jobId: integer
        @return troveMap: dictionary of troveSpecs to built troves
        """

        if type(jobId) != list:
            jobIds = [ jobId, ]
        else:
            jobIds = jobId

        jobIdsStr = ','.join(map(str, jobIds))

        # Do the commit
        startTime = time.time()
        jobs = [ self._getJob(x) for x in jobIds ]
        log.info('Starting commit of job %s', jobIdsStr)

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
            log.info('changeset saved to %s' % writeToFile)
            log.info('committing changeset to repository')
            self._client.repos.commitChangeSetFile(writeToFile)

        if self._sanityCheckCommits:
            # sanity check repository
            log.info('checking repository for sanity')
            jobList = []
            for job in data.itervalues():
                for arch in job.itervalues():
                    for n, v, f in arch:
                        if n.startswith('group-'): continue
                        jobList.append((n, (None, None), (v, f), True))
            try:
                cs = self._client.repos.createChangeSet(jobList, withFiles=True,
                                                        withFileContents=False)
            except Exception, e:
                self._errorEvent.setError(Exception, e)
                if self._topLevel:
                    self._errorEvent.raiseError()

        log.info('Commit of job %s completed in %.02f seconds',
                 jobIdsStr, time.time() - startTime)

        troveMap = {}
        for troveTupleDict in data.itervalues():
            for buildTroveTuple, committedList in troveTupleDict.iteritems():
                troveMap[buildTroveTuple] = committedList

        self._helper.client.commitSucceeded(data)

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
        'Fake rMake hook'


class _StatusOnlyDisplay(monitor.JobLogDisplay):
    """
    Display only job and trove status. No log output.

    Copied from bob3
    """

    # R0901 - Too many ancestors
    # pylint: disable-msg=R0901

    def _troveLogUpdated(self, (jobId, troveTuple), state, status):
        """
        Don't care about trove logs
        """

    def _trovePreparingChroot(self, (jobId, troveTuple), host, path):
        """
        Don't care about resolving/installing chroot
        """

    def _tailBuildLog(self, jobId, troveTuple):
        """
        Don't care about the build log
        """

    def _stopTailing(self, jobId, troveTuple):
        """
        Don't care about the build log
        """
