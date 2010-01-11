#
# Copyright (c) 2009 rPath, Inc.
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
from updatebot.build.constants import JobStatus

from updatebot.errors import JobNotCompleteError

log = logging.getLogger('updatebot.build')

class Dispatcher(object):
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


    def __init__(self, builder, maxSlots):
        self._builder = builder
        self._maxSlots = maxSlots
        self._slots = maxSlots

        self._maxStartSlots = 10
        self._startSlots = self._maxStartSlots

        self._maxCommitSlots = 2
        self._commitSlots = self._maxCommitSlots

        self._starter = JobStarter(self._builder)
        self._monitor = JobMonitor(self._builder._helper.client)
        self._committer = JobCommitter(self._builder)

        # jobId: (trv, status, commitData)
        self._jobs = {}

        self._failures = []

    def buildmany(self, troveSpecs):
        """
        Build as many packages as possible until we run out of slots.
        """

        # Must have at least one trove to build, otherwise will end up in
        # an infinite loop.
        if not troveSpecs:
            return {}

        # Sort troves into buckets.
        troves = self._builder.orderJobs(troveSpecs)

        while troves or not self._jobDone():
            # Only create more jobs once the last batch has been started.
            if self._startSlots == self._maxStartSlots:
                # fill slots with available troves
                while (troves and self._slots and self._startSlots and
                       self._availableFDs()):
                    # get trove to work on
                    trove = troves.pop()

                    # start build job
                    self._starter.startJob(trove)
                    self._slots -= 1
                    self._startSlots -= 1

            # get started status
            for jobId, trove in self._starter.getStatus():
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

                    if self._slots > self._maxSlots:
                        log.critical('slots is greater than maxSlots')

            # submit any jobs that are ready to commit as long as there are
            # commit slots
            toCommit = set()
            for jobId, (trove, status, result) in self._jobs.iteritems():
                # don't try to commit anything if there are no free commit
                # slots.
                if not self._commitSlots:
                    break
                # batch up all jobs that are ready to be committed
                if status == buildjob.JOB_STATE_BUILT:
                    # update status to !BUILT so that we don't try to commit
                    # this job more than once.
                    self._jobs[jobId][1] = JobStatus.JOB_COMMITTING
                    toCommit.add(jobId)

            # commit all available jobs at one time.
            if toCommit:
                self._committer.commitJob(tuple(toCommit))
                self._commitSlots -= 1

            # process monitor errors
            for jobId, error in self._monitor.getErrors():
                self._slots += 1
                self._jobs[jobId][1] = JobStatus.ERROR_MONITOR_FAILURE
                self._failures.append((jobId, error))

            # check for commit status
            for jobId, result in self._committer.getStatus():
                # unbatch commit jobs
                if not isinstance(jobId, tuple):
                    jobId = (jobId, )
                for jobId in jobId:
                    self._jobs[jobId][2] = result
                    self._commitSlots += 1

            # process committer errors
            for jobId, error in self._committer.getErrors():
                # unbatch commit jobs
                if not isinstance(jobId, tuple):
                    jobId = (jobId, )
                for jobId in jobId:
                    self._jobs[jobId][1] = JobStatus.ERROR_COMMITTER_FAILURE
                    self._failures.append((jobId, error))
                    self._commitSlots += 1

                    # Flag job as failed so that monitor worker will exit properly.
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

    def _jobDone(self):
        """
        Check if all jobs are complete.
        """

        if not len(self._jobs):
            return False

        for jobId, (trove, status, result) in self._jobs.iteritems():
            if status not in self._completed:
                return False
        return True

    def _availableFDs(self, setMax=False):
        """
        Get 80% of available file descriptors in hopes of not running out.
        """

        avail = util.getAvailableFileDescriptors(setMax=setMax)
        return math.floor(0.8 * avail)


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

    def __init__(self, builder, maxSlots):
        Dispatcher.__init__(self, builder, maxSlots)

        # Disable commits by removing all commit slots.
        self._maxCommitSlots = 0
        self._commitSlots = 0

    def buildmany(self, troveSpecs):
        """
        Build all packages in seperate jobs, then commit.
        """

        results, self._failures = Dispatcher.buildmany(self, troveSpecs)

        # Make sure there are no failures.
        assert not self._failures

        for jobId, (trove, status, result) in self._jobs.iteritems():
            # Make sure all jobs are built.
            if status != buildjob.JOB_STATE_BUILT:
                raise JobNotCompleteError(jobId=jobId)

        # If we get here, all jobs have built successfully and are ready to be
        # committed.
        jobIds = self._jobs.keys()
        res = self._builder.commit(jobIds)

        return res, self._failures
