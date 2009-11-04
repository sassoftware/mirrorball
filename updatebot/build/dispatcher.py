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

import time
import logging

from rmake.build import buildjob

from updatebot.build.monitor import JobStarter
from updatebot.build.monitor import JobMonitor
from updatebot.build.monitor import JobCommitter
from updatebot.build.constants import JobStatus

log = logging.getLogger('updatebot.build')

class Dispatcher(object):
    """
    Manage building a list of troves in a way that doesn't bring rMake to its
    knees.
    """

    _completed = (
        JobStatus.ERROR_MONITOR_FAILURE,
        JobStatus.ERROR_COMITTER_FAILURE,
        buildjob.JOB_STATE_FAILED,
        buildjob.JOB_STATE_COMMITTED,
    )

    _slotdone = (
        JobStatus.ERROR_MONITOR_FAILURE,
        JobStatus.ERROR_COMITTER_FAILURE,
        buildjob.JOB_STATE_FAILED,
        buildjob.JOB_STATE_BUILT,
    )


    def __init__(self, builder, maxSlots):
        self._builder = builder
        self._maxSlots = maxSlots
        self._slots = maxSlots

        self._maxStartSlots = 10
        self._startSlots = self._maxStartSlots

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

        troves = list(troveSpecs)
        troves.reverse()

        while troves or not self._jobDone():
            # Only create more jobs once the last batch has been started.
            if self._startSlots == self._maxStartSlots:
                # fill slots with available troves
                while troves and self._slots and self._startSlots:
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
                    assert self._slots <= self._maxSlots

                # commit any jobs that are done building
                if status == buildjob.JOB_STATE_BUILT:
                    self._committer.commitJob(jobId)

            # check for commit status
            for jobId, result in self._committer.getStatus():
                self._jobs[jobId][2] = result

            # process monitor errors
            for jobId, error in self._monitor.getErrors():
                self._slots += 1
                self._jobs[jobId][1] = JobStatus.ERROR_MONITOR_FAILURE
                self._failures.append((jobId, error))

            # process committer errors
            for jobId, error in self._committer.getErrors():
                self._jobs[jobId][1] = JobStatus.ERROR_COMITTER_FAILURE
                self._failures.append((jobId, error))

            # Wait for a bit before polling again.
            time.sleep(3)

        results = {}
        for jobId, (trove, status, result) in self._jobs.iteritems():
            # log failed jobs
            if status == buildjob.JOB_STATE_FAILED or not result:
                log.info('[%s] failed job: %s' % (jobId, trove))
            else:
                results.update(result)

        # report failures
        for job, error in self._failures:
            log.error('[%s] failed with error: %s' % (job, error))

        return results

    def _jobDone(self):
        if not len(self._jobs):
            return False

        for jobId, (trove, status, result) in self._jobs.iteritems():
            if status not in self._completed:
                return False
        return True
