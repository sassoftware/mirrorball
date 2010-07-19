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

from updatebot.build.constants import JobStatus
from updatebot.build.dispatcher import AbstractDispatcher

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

        self._maxCommitSlots = 1
        self._commitSlots = self._maxCommitSlots

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
