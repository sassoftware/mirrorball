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
New implementation of builder module that uses rMake's message bus for job
monitoring.
"""

import math
import time
import logging

from rmake.build import buildjob

from updatebot.lib import util
from updatebot.build.monitor import JobStarter
from updatebot.build.monitor import JobMonitor
from updatebot.build.monitor import JobCommitter
from updatebot.build.monitor import JobRebuildStarter
from updatebot.build.monitor import JobPromoter
from updatebot.build.constants import JobStatus

from updatebot.errors import JobsFailedError
from updatebot.errors import JobNotCompleteError

log = logging.getLogger('updatebot.build')

class AbstractDispatcher(object):
    """
    Abstract class for managing builds.
    """

    _completed = ()

    def __init__(self, builder, maxSlots, retries=0):
        self._builder = builder
        self._slots = util.BoundedCounter(0, maxSlots, maxSlots)
        self._retries = retries

        # jobId: (trv, status, commitData)
        self._jobs = {}
        self._failures = []

    def _jobDone(self):
        """
        Check if all jobs are complete.
        """

        log.info('waiting for the following jobs: %s' %
            ', '.join([ '%s:%s' % (x, self._jobs[x][1]) for x in self._jobs
            if self._jobs[x][1] not in self._completed]))

        if not len(self._jobs):
            log.debug('_jobs empty... guess we need to wait')
            log.debug('%s' % str(self._jobs))
            return False

        for jobId, (trove, status, result) in self._jobs.iteritems():
            log.debug('STATUS: %s' % status)
            if status == buildjob.JOB_STATE_FAILED:
                log.error('[%s] failed job: %s' % (jobId, trove))
            if status not in self._completed:
                log.debug('%s %s %s not in _completed' % (jobId, str(status), str(result)))
                return False

        return True

    def _availableFDs(self, setMax=False):
        """
        Get 80% of available file descriptors in hopes of not running out.
        """

        avail = util.getAvailableFileDescriptors(setMax=setMax)
        return math.floor(0.8 * avail)


class Dispatcher(AbstractDispatcher):
    """
    Manage building a list of troves in a way that doesn't bring rMake to its
    knees.
    """

    _completed = (
        JobStatus.ERROR_MONITOR_FAILURE,
        JobStatus.ERROR_COMMITTER_FAILURE,
        buildjob.JOB_STATE_FAILED,
        buildjob.JOB_STATE_COMMITTED,
    )

    _slotdone = (
        buildjob.JOB_STATE_FAILED,
        buildjob.JOB_STATE_BUILT,
    )

    _starterClass = JobStarter
    _monitorClass = JobMonitor
    _committerClass = JobCommitter

    def __init__(self, builder, maxSlots, retries=0):
        AbstractDispatcher.__init__(self, builder, maxSlots, retries=retries)

        self._startSlots = util.BoundedCounter(0, 10, 10)
        #self._commitSlots = util.BoundedCounter(0, 2, 2)
        self._commitSlots = util.BoundedCounter(0, 1, 1)

        self._starter = self._starterClass((self._builder, ),
                retries=self._retries)
        self._monitor = self._monitorClass((self._builder._helper.client, ),
                retries=self._retries)
        self._committer = self._committerClass((self._builder, ),
                retries=self._retries)

    def buildmany(self, troveSpecs):
        """
        Build as many packages as possible until we run out of slots.
        """

        # Must have at least one trove to build, otherwise will end up in
        # an infinite loop.
        if not troveSpecs:
            return {}, self._failures

        # Sort troves into buckets.
        troves = self._builder.orderJobs(troveSpecs)


        while troves or not self._jobDone():
            # Only create more jobs once the last batch has been started.
            if self._startSlots == self._startSlots.upperlimit:
                # fill slots with available troves
                while (troves and self._slots and self._startSlots and
                       self._availableFDs()):
                    # get trove to work on
                    trove = troves.pop(0)
                    # start build job
                    self._starter.startJob(trove)
                    self._slots -= 1
                    self._startSlots -= 1

            # get started status
            for trove, jobId in self._starter.getStatus():
                self._jobs[jobId] = [trove, JobStatus.JOB_NOT_STARTED, None]
                self._startSlots += 1
                self._monitor.monitorJob(jobId)

            # process starter errors
            for trove, error in self._starter.getErrors():
                self._startSlots += 1
                self._slots += 1
                self._failures.append((trove, error))

            # update job status changes
            for jobId, status in self._monitor.getStatus():
                self._jobs[jobId][1] = status
                # free up the slot once the job is built
                if status in self._slotdone:
                    self._slots += 1

                    if self._slots > self._slots.upperlimit:
                        log.critical('slots is greater than maxSlots')

            # submit any jobs that are ready to commit as long as there are
            # commit slots
            toCommit = self._getCommitJobs()
            # commit all available jobs at one time.
            if toCommit:
                for jobId in toCommit:
                    # update status to !BUILT so that we don't try to commit
                    # this job more than once.
                    self._jobs[jobId][1] = JobStatus.JOB_COMMITTING

                self._committer.commitJob(tuple(toCommit))
                self._commitSlots -= 1

            # process monitor errors
            for jobId, error in self._monitor.getErrors():
                self._slots += 1
                self._jobs[jobId][1] = JobStatus.ERROR_MONITOR_FAILURE
                self._failures.append((jobId, error))

            # check for commit status
            for jobId, result in self._committer.getStatus():
                self._commitSlots += 1
                # unbatch commit jobs
                if not isinstance(jobId, tuple):
                    jobId = (jobId, )
                for jobId in jobId:
                    self._jobs[jobId][2] = result

            # process committer errors
            for jobId, error in self._committer.getErrors():
                self._commitSlots += 1
                # unbatch commit jobs
                if not isinstance(jobId, tuple):
                    jobId = (jobId, )
                for jobId in jobId:
                    self._jobs[jobId][1] = JobStatus.ERROR_COMMITTER_FAILURE
                    self._failures.append((jobId, error))

                    # Flag job as failed so that monitor worker will exit
                    # properly.
                    self._builder.setCommitFailed(jobId, reason=str(error))

            # Wait for a bit before polling again.
            time.sleep(3)

        # report failures
        for job, error in self._failures:
            log.error('[%s] failed with error: %s' % (job, error))

        results = {}
        for jobId, (trove, status, result) in self._jobs.iteritems():
            # don't return errors if we intentionaly didn't commit.
            built = buildjob.JOB_STATE_BUILT
            if status == built and built in self._completed and not result:
                continue
            # log failed jobs
            if status == buildjob.JOB_STATE_FAILED or not result:
                log.info('[%s] failed job: %s' % (jobId, trove))
                self._failures.append((jobId, status))
            else:
                results.update(result)

        return results, self._failures

    def _getCommitJobs(self):
        """
        Get a set of jobIds that are ready to be committed.
        """

        toCommit = set()

        # don't try to commit anything if there are no free commit slots.
        if not self._commitSlots:
            return toCommit

        for jobId, (trove, status, result) in self._jobs.iteritems():
            # batch up all jobs that are ready to be committed
            if status == buildjob.JOB_STATE_BUILT:
                toCommit.add(jobId)

        return toCommit


class NonCommittalDispatcher(Dispatcher):
    """
    A dispatcher class that is configured to not commit until all jobs are
    complete.
    """

    # States where the job is considered complete.
    _completed = (
        JobStatus.ERROR_MONITOR_FAILURE,
        JobStatus.ERROR_COMMITTER_FAILURE,
        buildjob.JOB_STATE_FAILED,
        buildjob.JOB_STATE_BUILT,
    )

    def __init__(self, builder, maxSlots, retries=0):
        Dispatcher.__init__(self, builder, maxSlots, retries=retries)

        # Disable commits by removing all commit slots.
        self._commitSlots = util.BoundedCounter(0, 0, 0)

    def buildmany(self, troveSpecs):
        """
        Build all packages in seperate jobs, then commit.
        """

        # Must have at least one trove to build, otherwise will end up in
        # an infinite loop.
        if not troveSpecs:
            return {}, self._failures

        results, self._failures = Dispatcher.buildmany(self, troveSpecs)

        # Make sure there are no failures.
        if self._failures:
            for failure in self._failures:
                log.error('failed: %s' % (failure, ))
            raise JobsFailedError(jobIds=self._failures, why='Failed to build '
                'all troves, refusing to commit')

        for jobId, (trove, status, result) in self._jobs.iteritems():
            # Make sure all jobs are built.
            if status != buildjob.JOB_STATE_BUILT:
                raise JobNotCompleteError(jobId=jobId)

        # If we get here, all jobs have built successfully and are ready to be
        # committed.
        jobIds = self._jobs.keys()
        res = self._builder.commit(jobIds)

        return res, self._failures

    def watchmany(self, jobIds):
        """
        Watch a list of jobIds. Blocks until jobs are complete.
        @param jobIds: list of jobIds
        @type jobIds: list(int, ...)
        """

        # Start monitoring each job.
        for jobId in jobIds:
            self._jobs[jobId] = [None, JobStatus.JOB_NOT_STARTED, None]
            self._monitor.monitorJob(jobId)

        # Wait for jobs to complete.
        while not self._jobDone():
            # Update job status changes.
            for jobId, status in self._monitor.getStatus():
                self._jobs[jobId][1] = status

        # Make sure all jobs are built.
        for jobId, (trove, status, result) in self._jobs.iteritems():
            if status != buildjob.JOB_STATE_BUILT:
                raise JobNotCompleteError(jobId=jobId)


class MultiVersionDispatcher(Dispatcher):
    """
    A dispatcher implementation for building many packages with multiple
    versions of the same package.
    """

    def __init__(self, builder, maxSlots, waitForAllVersions=False, retries=0):
        Dispatcher.__init__(self, builder, maxSlots, retries=retries)

        self._waitForAllVersions = waitForAllVersions

        self._commitSlots = util.BoundedCounter(0, 1, 1)

        # Mapping of pkgname to ordered list of trove specs
        self._pkgs = {}
        self._failedpkgs = {}

    def buildmany(self, troveSpecs):
        """
        Build as many packages as possible until we run out of slots.
        """

        for spec in troveSpecs:
            self._pkgs.setdefault(spec[0], []).append(spec)
        for name, specLst in self._pkgs.iteritems():
            self._pkgs[name] = sorted(specLst)

        troveSpecs = sorted(troveSpecs)

        trvMap, failed = Dispatcher.buildmany(self, troveSpecs)

        if self._failedpkgs:
            log.info('The following jobs failed to commit')
            for name, jobLst in self._failedpkgs.iteritems():
                log.info('%s: %s' % (name, jobLst))

        return trvMap, failed

    def _getCommitJobs(self):
        """
        Get a set of jobIds that are ready to be committed.
        """

        toCommit = set()

        # don't try to commit anything if there are no free commit slots.
        if not self._commitSlots:
            return toCommit

        built = {}
        for jobId, (trove, status, result) in self._jobs.iteritems():
            # batch up all jobs that are ready to be committed
            if status == buildjob.JOB_STATE_BUILT:
                built.setdefault(trove[0], dict())[trove] = jobId

            # Check if any packages have failed to commit.
            elif (status == JobStatus.ERROR_COMMITTER_FAILURE and 
                  trove[0] not in self._failedpkgs):
                self._failedpkgs[trove[0]] = [jobId, ]

        for name, jobDict in built.iteritems():
            # Wait for all versions of a package to build.
            if ((self._waitForAllVersions and
                 len(jobDict) == len(self._pkgs[name])) or
                # Wait for the first version to be built.
                (not self._waitForAllVersions and
                 self._pkgs[name] and
                 self._pkgs[name][0] in jobDict)):
                # Pop off the first trove spec to commit.
                spec = self._pkgs[name].pop(0)

                jobId = jobDict[spec]

                # If a build of one version of a package fails to commit, mark
                # all subsiquent versions as failed.
                if name in self._failedpkgs:
                    self._failedpkgs[name].append(jobId)
                    self._jobs[jobId][1] = JobStatus.ERROR_COMMITTER_FAILURE
                    continue

                toCommit.add(jobId)

        for name, jobDict in built.iteritems():
            order = []
            for spec in self._pkgs[name]:
                if spec not in jobDict:
                    break
                order.append(jobDict[spec])

            if order:
                log.info('ordered built jobs for %s: %s' % (name, order))

        return toCommit


class RebuildDispatcher(MultiVersionDispatcher):
    """
    Dispatcher for coordinating massive package rebuilds.
    """

    _starterClass = JobRebuildStarter

    def __init__(self, builder, maxSlots, useLatest=None,
        additionalResolveTroves=None, retries=0):
        MultiVersionDispatcher.__init__(self, builder, maxSlots,
            waitForAllVersions=True, retries=retries)

        self._starter = self._starterClass((builder, useLatest,
            additionalResolveTroves))


class PromoteDispatcher(Dispatcher):
    """
    Dispatcher class that promotes the builds to the production label once they
    are complete.
    """

    _completed = (
        JobStatus.ERROR_MONITOR_FAILURE,
        JobStatus.ERROR_COMMITTER_FAILURE,
        JobStatus.ERROR_PROMOTE_FAILURE,
        buildjob.JOB_STATE_FAILED,
        JobStatus.JOB_PROMOTED,
    )

    _promoterClass = JobPromoter

    def __init__(self, builder, maxSlots, retries=0):
        Dispatcher.__init__(self, builder, maxSlots, retries=retries)

        self._promoteSlots = util.BoundedCounter(0, 1, 1)

        self._promoter = self._promoterClass((self._builder._conaryhelper,
            self._builder._cfg.targetLabel), retries=retries)

        self._status = {}

    def _jobDone(self):
        # Override the job done method from the parent to hook into the
        # build loop. This is kinda dirty, but I don't really have a
        # better idea at the moment.

        done = Dispatcher._jobDone(self)
        if done:
            return done

        self._promoteJobs()

        return done

    def _promoteJobs(self):
        """
        Handle the promote section of the build loop.
        """

        # Find jobs in the Committed state that need to be promoted
        if self._promoteSlots:
            toPromote = []
            for jobId, (trove, state, result) in self._jobs.iteritems():
                # not ready to be promoted
                if state != buildjob.JOB_STATE_COMMITTED:
                    continue

                # It might take a few iterations through the loop for the
                # result to show up.
                if not result:
                    log.info('No results state is %s' % str(state))
                    continue

                # Make result hashable
                res = tuple([ (x, tuple(y)) for x, y in result.iteritems() ])

                toPromote.append((jobId, res))
                self._status[jobId] = time.time()

            if toPromote:
                for jobId, res in toPromote:
                    self._jobs[jobId][1] = JobStatus.JOB_PROMOTING

                self._promoteSlots -= 1
                self._promoter.promoteJob(toPromote)

        # Gather results
        for result in self._promoter.getStatus():
            log.warn('WE GOT RESULTS FROM PROMOTER')
            self._promoteSlots += 1
            for jobId, promoted in result:
                self._jobs[jobId][2] = promoted
                self._jobs[jobId][1] = JobStatus.JOB_PROMOTED
                log.warn('JOB STATUS: %s %s' % (str(self._jobs[jobId][1]),
                                                    str(self._jobs[jobId][2])))
        # Gather errors
        for jobs, error in self._promoter.getErrors():
            self._promoteSlots += 1
            for jobId in jobs:
                self._jobs[jobId][1] = JobStatus.ERROR_PROMOTE_FAILURE
                self._failures.append((jobId, error))
