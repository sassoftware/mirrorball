#
# Copyright (c) 2010 rPath, Inc.
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
Implementation of dispatchers and status monitors that is appendable and uses
temporary job objects to return status, errors and results, rather than blocking
on everything that has been submitted to finish building.
"""

import time
import logging
from threading import Thread

from rmake.build import buildjob

from updatebot.lib import util
from updatebot.build.constants import JobStatus
from updatebot.build.dispatcher import AbstractDispatcher

from updatebot.build.monitor import JobStarter
from updatebot.build.monitor import JobMonitor
from updatebot.build.monitor import JobCommitter
from updatebot.build.local import LocalGroupCooker
from updatebot.build.local import LocalChangeSetCommitter

from updatebot.errors import BuildFailedError
from updatebot.errors import ResultsNotReadyError

log = logging.getLogger('updatebot.build')

class Data(object):
    """
    Opaque data object for the dispatcher store attributes of the build.
    """

class Status(object):
    """
    Base container class for job related data.
    """

    def __init__(self, jobId):
        self.jobId = jobId
        self._isDone = False

        self._results = None
        self._error = None
        self._status = None

        self.data = Data()

    @property
    def isDone(self):
        return self._isDone

    @property
    def results(self):
        if self._results is None:
            raise ResultsNotReadyError(trove=self.jobId)
        else:
            return self._results

    def setResults(self, results):
        """
        Store the results of the job.
        """

        self._results = results
        self._isDone = True

    def setError(self, error):
        """
        Store the error and call an error handler.
        """

        self._error = error
        self._handleError()

    def _handleError(self):
        """
        Handle error conditions.
        """

        raise BuildFailedError(trove=self.jobId, error=self._error)

    def setStatus(self, statusStr):
        """
        Set status information.
        """

        self._status = statusStr
        log.info('%s: %s' % (self.jobId, self._status))


class LocalDispatcher(AbstractDispatcher, Thread):
    """
    Coordinate multiple local builds.
    """

    statusClass = Status

    _slotdone = (
        JobStatus.JOB_BUILT,
    )

    _completed = (
        JobStatus.JOB_FAILED,
        JobStatus.JOB_COMMITTED,
    )

    def __init__(self, builder, maxSlots):
        AbstractDispatcher.__init__(self, builder, maxSlots)
        Thread.__init__(self)

        self._commitSlots = util.BoundedCounter(0, 1, 1)

        self._cooker = LocalGroupCooker(self._builder)
        self._committer = LocalChangeSetCommitter(self._builder)

        self._order = []
        self._started = False
        self._done = False

        self.daemon = True

    def _getNotStarted(self):
        """
        Get the list of jobs that have not yet been started.
        """

        return [ x for x in self._jobs.itervalues()
                 if x[1] == JobStatus.JOB_NOT_STARTED ]

    def run(self):
        """
        Polling loop to monitor and update job status.
        """

        totalWait = 0
        committed = []
        while not self._done:
            # Start any jobs that are waiting to be started as long as there
            # are available slots.
            notStarted = self._getNotStarted()
            while self._slots and notStarted:
                self._slots -= 1
                trove, status, res = notStarted[0]
                self._cooker.buildGroup((trove, res.data.flavorFilter))

                self._jobs[trove][1] = JobStatus.JOB_BUILDING
                res.setStatus('building')

                notStarted = self._getNotStarted()

            # Check cooker status.
            for trove, csFileName, result in self._cooker.getStatus():
                self._slots += 1
                trove, status, res = self._jobs[trove]

                self._jobs[trove][1] = JobStatus.JOB_BUILT
                res.setStatus('built')

                res.data.buildResults = result
                res.data.csFileName = csFileName

            # Check for cooker errors.
            for trove, error in self._cooker.getErrors():
                self._slots += 1
                self._jobs[trove][1] = JobStatus.JOB_FAILED
                self._jobs[trove][2].setStatus('build failed')
                self._jobs[trove][2].setError(error)

            # Find jobs that are ready to be committed. Jobs must be committed
            # in the order that they were submitted.
            for trove in self._order:
                # continue if this trove has already been committed.
                if self._jobs[trove][1] in self._completed:
                    continue

                # Make sure everything has committed in order.
                if self._jobs[trove][1] not in self._slotdone:
                    break

                # Make sure there are open slots.
                if self._commitSlots == 0:
                    break

                # Commit the job.
                if self._commitSlots > 0:
                    self._commitSlots -= 1
                    self._jobs[trove][2].setStatus('committing')
                    self._jobs[trove][1] = JobStatus.JOB_COMMITTING

                    changeSetFile = self._jobs[trove][2].data.csFileName
                    self._committer.commitChangeSet((trove, changeSetFile))

                assert self._commitSlots > -1

            # Check for commit results.
            for trove, results in self._committer.getStatus():
                self._commitSlots += 1
                self._jobs[trove][1] = JobStatus.JOB_COMMITTED
                res = self._jobs[trove][2]
                res.setStatus('committed')
                res.setResults(res.data.buildResults)
                committed.append(trove)

            # Check for commit errors.
            for trove, error in self._committer.getErrors():
                self._jobs[trove][1] = JobStatus.JOB_FAILED
                self._jobs[trove][2].setStatus('commit failed')
                self._jobs[trove][2].setError(error)

            time.sleep(3)
            totalWait += 3

            # Only log slot status once a minute
            if not totalWait % 60:
                log.info('build slots: %s' % self._slots)
                log.info('commit slots: %s' % self._commitSlots)

    def build(self, troveSpec, flavorFilter=None):
        """
        Add one trove spec to the build queue.
        """

        # Make sure this instance hasn't been marked as done.
        assert not self._done

        # Require at least one trove.
        if not troveSpec:
            return None

        # Wait for an available slot.
        while not self._slots:
            time.sleep(3)

        if troveSpec not in self._jobs:
            status = self.statusClass(troveSpec)
            status.data.flavorFilter = frozenset(flavorFilter)

            self._jobs[troveSpec] = [troveSpec, JobStatus.JOB_NOT_STARTED,
                status]
            self._order.append(troveSpec)
        else:
            log.warn('already building/built requested trove: %s=%s'
                     % (troveSpec[0], troveSpec[1]))
            return self._jobs[troveSpec][2]

        if not self._started:
            self.start()
            self._started = True

        return status

    def done(self):
        """
        Mark this worker as complete. This stops the worker thread. Note that
        once this is called this instance may no longer be used for building.
        """

        self._done = True


class JobBasedDispatcher(AbstractDispatcher, Thread):
    """
    Dispatcher for coordinating builds of multiple troves.
    """

    statusClass = Status

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

    def __init__(self, builder, maxSlots):
        AbstractDispatcher.__init__(self, builder, maxSlots)
        Thread.__init__(self)

        self._startSlots = util.BoundedCounter(0, 10, 10)
        self._commitSlots = util.BoundedCounter(0, 2, 2)

        self._starter = self._starterClass(self._builder)
        self._monitor = self._monitorClass(self._builder._helper.client)
        self._committer = self._committerClass(self._builder)

        self._troves = {}
        self._done = False
        self._started = False

        self.daemon = True

    def _getNotStarted(self):
        """
        Get the list of jobs that have not yet been started.
        """

        return [ x for x in self._troves.itervalues()
                 if x[1] == JobStatus.JOB_NOT_STARTED ]

    def run(self):
        """
        Build as many packages as possible until we run out of slots.
        """

        while not self._done:
            # Only create more jobs once the last batch has been started.
            if self._startSlots == self._startSlots.upperlimit:
                # fill slots with available troves
                notStarted = self._getNotStarted()
                while notStarted and self._slots and self._startSlots:
                    # get trove to work on
                    trove, status, res = notStarted[0]

                    # start build job
                    self._starter.startJob(trove)
                    self._troves[trove][1] = JobStatus.JOB_STARTING
                    res.setStatus('starting')

                    self._slots -= 1
                    self._startSlots -= 1

                    notStarted = self._getNotStarted()

            # get started status
            for trove, jobId in self._starter.getStatus():
                self._jobs[jobId] = self._troves[trove]
                self._jobs[jobId][2].setStatus('started')
                self._startSlots += 1
                self._monitor.monitorJob(jobId)

            # process starter errors
            for trove, error in self._starter.getErrors():
                self._startSlots += 1
                self._slots += 1
                self._failures.append((trove, error))
                self._troves[trove][2].setStatus('start failed')
                self._troves[trove][2].setError(error)

            # update job status changes
            for jobId, status in self._monitor.getStatus():
                self._jobs[jobId][1] = status
                # free up the slot once the job is built
                if status in self._slotdone:
                    self._slots += 1

                    if self._slots > self._slots.upperlimit:
                        log.critical('slots is greater than maxSlots')

                    res = self._jobs[jobId][2]
                    if status == buildjob.JOB_STATE_FAILED:
                        res.setError('job failed')
                        res.setStatus('job failed')
                    else:
                        res.setStatus('built')

            # submit any jobs that are ready to commit as long as there are
            # commit slots
            toCommit = self._getCommitJobs()
            # commit all available jobs at one time.
            if toCommit:
                for jobId in toCommit:
                    # update status to !BUILT so that we don't try to commit
                    # this job more than once.
                    self._jobs[jobId][1] = JobStatus.JOB_COMMITTING
                    self._jobs[jobId][2].setStatus('committing')

                self._committer.commitJob(tuple(toCommit))
                self._commitSlots -= 1

            # process monitor errors
            for jobId, error in self._monitor.getErrors():
                self._slots += 1
                self._jobs[jobId][1] = JobStatus.ERROR_MONITOR_FAILURE
                self._jobs[jobId][2].setStatus('monitor failed')
                self._jobs[jobId][2].setError(error)
                self._failures.append((jobId, error))

            # check for commit status
            for jobId, result in self._committer.getStatus():
                self._commitSlots += 1
                # unbatch commit jobs
                if not isinstance(jobId, tuple):
                    jobId = (jobId, )
                for jobId in jobId:
                    self._jobs[jobId][2].setResults(result)
                    self._jobs[jobId][2].setStatus('committed')

            # process committer errors
            for jobId, error in self._committer.getErrors():
                self._commitSlots += 1
                # unbatch commit jobs
                if not isinstance(jobId, tuple):
                    jobId = (jobId, )
                for jobId in jobId:
                    self._jobs[jobId][1] = JobStatus.ERROR_COMMITTER_FAILURE
                    self._jobs[jobId][2].setError(error)
                    self._jobs[jobId][2].setStatus('commit failed')
                    self._failures.append((jobId, error))

                    # Flag job as failed so that monitor worker will exit properly.
                    self._builder.setCommitFailed(jobId, reason=str(error))

            # Wait for a bit before polling again.
            time.sleep(3)

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

    def build(self, troveSpec):
        """
        Add one trove spec to the build queue.
        """

        # Make sure this instance hasn't been marked as done.
        assert not self._done

        # Require at least one trove.
        if not troveSpec:
            return None

        # Wait for an available slot.
        while not self._slots:
            time.sleep(3)

        if troveSpec not in self._troves:
            status = self.statusClass(troveSpec)

            self._troves[troveSpec] = [troveSpec, JobStatus.JOB_NOT_STARTED,
                status]
        else:
            log.warn('already building/built requested trove: %s=%s'
                     % (troveSpec[0], troveSpec[1]))
            return self._jobs[troveSpec][2]

        if not self._started:
            self.start()
            self._started = True

        return status

    def done(self):
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
            if status == buildjob.JOB_STATE_FAILED or not result.isDone:
                log.info('[%s] failed job: %s' % (jobId, trove))
                self._failures.append((jobId, status))
            else:
                results.update(result.results)

        self._done = True
        return results, self._failures


class OrderedCommitDispatcher(JobBasedDispatcher):
    """
    Dispatcher for coordinating trove builds and committing in the order that
    the builds were submitted.
    """

    def __init__(self, builder, maxJobs):
        JobBasedDispatcher.__init__(self, builder, maxJobs)

        self._pkgs = {}

    def build(self, troveSpec):
        self._pkgs.setdefault(troveSpec[0], []).append(troveSpec)
        return JobBasedDispatcher.build(self, troveSpec)

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

        for name, troveMap in built.iteritems():
            if self._pkgs[name] and self._pkgs[name][0] in troveMap:
                spec = self._pkgs[name].pop(0)
                jobId = troveMap[spec]
                toCommit.add(jobId)

        if toCommit:
            waiting = sum([ len(x) for x in built.itervalues() ])
            log.info('committing %s of %s' % (len(toCommit), waiting))

        return toCommit
