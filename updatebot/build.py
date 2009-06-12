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

import xml
from Queue import Queue, Empty
from threading import Thread, RLock

from conary.deps import deps
from conary import conarycfg, conaryclient

from rmake import plugins
from rmake.build import buildcfg
from rmake.cmdline import helper, monitor, commit

from updatebot.lib import util
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
    """

    def __init__(self, cfg):
        self._cfg = cfg

        self._ccfg = conarycfg.ConaryConfiguration(readConfigFiles=False)
        self._ccfg.read(util.join(self._cfg.configPath, 'conaryrc'))
        self._ccfg.dbPath = ':memory:'
        self._ccfg.initializeFlavors()

        self._client = conaryclient.ConaryClient(self._ccfg)

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

        self._rmakeCfg = buildcfg.BuildConfiguration(readConfigFiles=False)
        self._rmakeCfg.read(util.join(self._cfg.configPath, 'rmakerc'))
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
        Build all packages in troveSpecs, 10 at a time, one per job.
        @param troveSpecs: list of trove specs
        @type troveSpecs: [(name, versionObj, flavorObj), ...]
        @return troveMap: dictionary of troveSpecs to built troves
        """

        troveSpecs = list(troveSpecs)
        def trvSort(a, b):
            """
            Sort troves tuples based on the first element.
            """

            return cmp(a[0], b[0])
        troveSpecs.sort(trvSort)

        index = 0
        jobs = {}
        for i, trv in enumerate(troveSpecs):
            if index not in jobs:
                jobs[index] = []

            jobs[index].append(trv)

            if i % 20 == 0:
                index += 1

        failed = set()
        results = {}
        for job in jobs.itervalues():
            res, fail = self._buildmany(job)
            failed.update(fail)
            results.update(res)

        return results, failed

    def _buildmany(self, troveSpecs):
        """
        Build a list of packages, one per job.
        @param troveSpecs: list of trove specs
        @type troveSpecs: [(name, versionObj, flavorObj), ...]
        @return troveMap: dictionary of troveSpecs to built troves
        """

        jobs = {}
        jobkeys = []
        for trv in troveSpecs:
            jobkeys.append(trv)
            jobs[trv] = self.start([trv, ])

        for trv in jobkeys:
            jobId = jobs[trv]
            job = self._getJob(jobId)
            self._wait(jobId)

        failed = set()
        results = {}
        for trv, jobId in jobs.iteritems():
            job = self._getJob(jobId)
            if job.isFailed():
                failed.add((trv, jobId))
            elif job.isFinished():
                try:
                    res = self.commit(jobId)
                    results.update(res)
                except JobFailedError:
                    failed.add((trv, jobId))

        return results, failed

    def buildmany2(self, troveSpecs):
        dispatcher = Dispatcher(self._cfg, 30)
        return dispatcher.buildmany(troveSpecs)

    def buildmany3(self, troveSpecs):
        dispatcher = Dispatcher2(self._cfg, 50)
        return dispatcher.buildmany(troveSpecs)

    def buildmany4(self, troveSpecs):
        dispatcher = Dispatcher3(self._cfg, 50)
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
            self._wait(jobId)

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
            # Don't set context for groups, they will already have the
            # correct flavors.
            if name.startswith('group-'):
                troves.append((name, version, flavor))
            elif ((name == 'kernel' or name in self._cfg.kernelModules)
                  and self._cfg.kernelFlavors):
                for context, flavor in self._cfg.kernelFlavors:
                    # Replace flag name to match package
                    if name != 'kernel':
                        flavor = deps.parseFlavor(str(flavor).replace('kernel', name))
                        # Don't build kernel modules with a .debug flag, that
                        # is only for kernels.
                        if flavor.stronglySatisfies(deps.parseFlavor('%s.debug' % name)):
                            continue
                    troves.append((name, version, flavor, context))
            elif name in self._cfg.packageFlavors:
                for context, flavor in self._cfg.packageFlavors[name]:
                    troves.append((name, version, flavor, context))
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

    def _wait(self, jobId):
        """
        Wait for a job to complete.
        @param jobId: rMake job ID
        @type jobId: integer
        """

        log.info('waiting for job [%s] to complete' % jobId)
        job = self._getJob(jobId)
        while not job.isFinished() and not job.isFailed():
            time.sleep(5)
            job = self._getJob(jobId)

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

        self._helper.client.startCommit(jobIds)
        succeeded, data = commit.commitJobs(self._helper.getConaryClient(),
                                            jobs,
                                            self._rmakeCfg.reposName,
                                            self._cfg.commitMessage)

        if not succeeded:
            self._helper.client.commitFailed(jobIds, data)
            raise CommitFailedError(jobId=jobIdsStr, why=data)

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

##
# Experimental threaded builder, beware of dragons
##

MESSAGE_TYPES = {
    0: 'log',
    'log': 0,
    1: 'results',
    'results': 1,
    2: 'error',
    'error': 2,
}

class StatusMessage(object):
    def __init__(self, name, trv, jobId, message, type=0):
        assert type in MESSAGE_TYPES
        self.name = name
        self.trv = trv
        self.jobId = jobId
        self.message = message
        self.type = type

    def __str__(self):
        msg = '%(name)s: %(trv)s [%(jobId)s] - '
        if self.type == MESSAGE_TYPES['results']:
            msg += 'done'
        else:
            msg += '%(message)s'
        return msg % self.__dict__

class BuildWorker(Thread):
    BuilderClass = Builder

    def __init__(self, cfg, toBuild, status, name=None, offset=0):
        Thread.__init__(self, name=name)

        self.setDaemon(True)

        self.name = name
        self.offset = offset
        self.toBuild = toBuild
        self.status = status
        self.builder = self.BuilderClass(cfg)

        self.trv = None
        self.jobId = None

    def run(self):
        time.sleep(self.offset * 5)
        while True:
            self.trv = self.toBuild.get()
            self.log('received trv')

            retries = 10
            built = False
            while not built and retries:
                retries -= 1
                try:
                    self._doBuild()
                except Exception, e:
                    built = False
                    self.log('traceback while building %s, retrying' % e)
                    continue
                built = True

            if not built:
                self.error('job failed')

            self.toBuild.task_done()

    def _doBuild(self):
        self.jobId = self.builder.start([self.trv, ])

        self.builder._wait(self.jobId)

        job = self.builder._getJob(self.jobId)
        if job.isFailed():
            self.error('job failed')

        else:
            try:
                res = self.builder.commit(self.jobId)
                self.results(res)
            except JobFailedError:
                self.error('job failed')

    def _status(self, msg, type=0):
        msg = StatusMessage(self.name, self.trv, self.jobId, msg, type)
        self.status.put(msg)

    def error(self, msg):
        self._status(msg, type=MESSAGE_TYPES['error'])

    def log(self, msg):
        self._status(msg, type=MESSAGE_TYPES['log'])

    def results(self, res):
        self._status(res, type=MESSAGE_TYPES['results'])

class Dispatcher(object):
    workerClass = BuildWorker

    def __init__(self, cfg, workerCount):
        self._cfg = cfg
        self._workerCount = workerCount

        self._workers = []
        self._started = False

        self._toBuild = Queue()
        self._status = Queue()

        self._trvs = {}

    def provisionWorkers(self):
        for i in range(self._workerCount):
            worker = self.workerClass(self._cfg, self._toBuild, self._status,
                                 name='Build Worker %s' % i, offset=i)
            self._workers.append(worker)

    def start(self):
        if self._started:
            return

        for wkr in self._workers:
            wkr.start()
        self._started = True

    def buildmany(self, trvSpecs):
        self.provisionWorkers()
        self.start()

        for trv in trvSpecs:
            self._trvs[trv] = []
            self._toBuild.put(trv)

        results, failed = self.monitorStatus()
        return results, failed

    def monitorStatus(self):
        done = False
        while not done:
            try:
                log.debug('checking for status messages')
                msg = self._status.get(timeout=5)
            except Empty:
                continue

            self._processMessage(msg)
            done = self._buildDone()

        return self._getResultsAndErrors()

    def _processMessage(self, msg):
        assert msg.trv in self._trvs
        self._trvs[msg.trv].append(msg)
        log.info(msg)

    def _buildDone(self):
        for trv, msgs in self._trvs.iteritems():
            if len(msgs) == 0:
                return False
            elif msgs[-1].type not in (MESSAGE_TYPES['results'], MESSAGE_TYPES['error']):
                return False
        return True

    def _getResultsAndErrors(self):
        errors = set()
        results = []
        for trv, msgs in self._trvs.iteritems():
            msg = msgs[-1]
            if msg.type == MESSAGE_TYPES['error']:
                errors.add((trv, msg.jobId))
            elif msg.type == MESSAGE_TYPES['results']:
                results.append(msg.message)
        return results, errors


class Dispatcher2(object):
    builderClass = Builder

    def __init__(self, cfg, workerCount):
        self._cfg = cfg
        self._workerCount = workerCount

        self._builder = self.builderClass(self._cfg)

        self._activeJobs = []
        self._commitJobs = []
        self._failedJobs = set()
        self._completedJobs = []

        self._results = {}

    def buildmany(self, troveSpecs):
        troveSpecs = list(troveSpecs)

        while len(troveSpecs):
            # Wait for some amount of jobs to complete.
            while len(self._activeJobs) >= self._workerCount:
                time.sleep(5)
                self._checkStatus()

            # Populate build queue.
            while len(self._activeJobs) < self._workerCount:
                trvSpec = troveSpecs.pop()
                self._start(trvSpec)

            # Commit completed jobs.
            self._commit()

        return self._results, self._failedJobs

    @jobInfoExceptionHandler
    def _start(self, troveSpec):
        jobId = self._builder.start([troveSpec, ])
        self._activeJobs.append((troveSpec, jobId))

    def _checkStatus(self):
        for troveSpec, jobId in self._activeJobs:
            log.info('Checking status of %s' % jobId)
            job = self._builder._getJob(jobId, retry=10)
            if job is None:
                log.warn('Failed to retrieve job information for %s' % jobId)
                import epdb; epdb.st()
            elif job.isFailed():
                self._failedJobs.add((troveSpec, jobId))
                self._activeJobs.remove((troveSpec, jobId))
            elif job.isFinished():
                self._commitJobs.append((troveSpec, jobId))
                self._activeJobs.remove((troveSpec, jobId))

            # Wait between each status check.
            #time.sleep(1)

    def _commit(self):
        for troveSpec, jobId in self._commitJobs:
            try:
                res = self._builder.commit(jobId)
                self._results.update(res)
                self._completedJobs.append(jobId)
            except JobFailedError:
                self._failedJobs.add((troveSpec, jobId))
            self._commitJobs.remove((troveSpec, jobId))


class CommitWorker(Thread):
    BuilderClass = Builder

    def __init__(self, cfg, toCommit, results, name=None):
        Thread.__init__(self, name=name)

        self.name = name
        self.toCommit = toCommit
        self.results = results
        self.builder = self.BuilderClass(cfg)

        self.setDaemon(True)

    def run(self):
        while True:
            trvSpec, jobId = self.toCommit.get()
            try:
                res = self.builder.commit(jobId)
                self.msg(0, trvSpec, jobId, res)
            except JobFailedError:
                self.msg(1, trvSpec, jobId)
            except Exception, e:
                log.critical('%s received exception: %s' % (self.name, e))

    def msg(self, rc, trvSpec, jobId, data=None):
        self.results.put((rc, ((trvSpec, jobId), data)))


class Dispatcher3(Dispatcher2):
    workerClass = CommitWorker

    def __init__(self, cfg, workerCount):
        Dispatcher2.__init__(self, cfg, workerCount)

        self._commitQueue = Queue()
        self._resultQueue = Queue()

        self._workers = []
        for i in range(10):
            worker = self.workerClass(self._cfg, self._commitQueue,
                self._resultQueue, name='Commit Worker %s' % i)
            worker.start()
            self._workers.append(worker)

    def _commit(self):
        for trvSpec, jobId in self._commitJobs:
            self._commitQueue.put((trvSpec, jobId))

        try:
            msg = self._resultQueue.get(False)
            while msg:
                rc, ((trvSpec, jobId), data) = msg
                if rc == 0:
                    self._results.update(data)
                    self._completedJobs.append(jobId)
                elif rc == 1:
                    self._failedJobs.add((trvSpec, jobId))
                msg = self._resultQueue.get(False)
        except Empty:
            pass
