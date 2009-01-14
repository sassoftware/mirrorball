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

from conary import conarycfg, conaryclient

from rmake import plugins
from rmake.build import buildcfg
from rmake.cmdline import helper, monitor, commit

from updatebot.lib import util
from updatebot.errors import JobFailedError, CommitFailedError

log = logging.getLogger('updateBot.build')

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
        self._monitorJob(jobId)
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

            if i % 50 == 0:
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
            job = self._helper.getJob(jobId)
            while not job.isFinished() and not job.isFailed():
                log.info('waiting for %s' % jobId)
                time.sleep(1)
                job = self._helper.getJob(jobId)

        failed = set()
        results = {}
        for trv, jobId in jobs.iteritems():
            job = self._helper.getJob(jobId)
            if job.isFailed():
                failed.add((trv, jobId))
            elif job.isFinished():
                try:
                    res = self.commit(jobId)
                    results.update(res)
                except JobFailedError:
                    failed.add((trv, jobId))

        return results, failed

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
            job = self._helper.getJob(jobId)
            while not job.isFinished() and not job.isFailed():
                time.sleep(1)
                job = self._helper.getJob(jobId)

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
            elif name == 'kernel' and self._cfg.kernelFlavors:
                for context, flavor in self._cfg.kernelFlavors:
                    troves.append((name, version, flavor, context))
            else:
                # Build all packages as x86 and x86_64.
                for context in self._cfg.archContexts:
                    troves.append((name, version, flavor, context))

        return troves

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
        job = self._helper.getJob(jobId)
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

        jobIdsStr = ','.join(jobIds)

        # Do the commit
        startTime = time.time()
        jobs = [ self._helper.getJob(x) for x in jobIds ]
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
