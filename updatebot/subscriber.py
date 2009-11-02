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

import copy
import time
import logging
import itertools
from threading import Thread
from Queue import Queue, Empty

from rmake.build import buildjob
from rmake.build import buildtrove
from rmake.cmdline import monitor

log = logging.getLogger('updatebot.subscriber')

class MessageTypes(object):
    """
    Class for storing message type constants.
    """

    LOG = 0
    DATA = 1
    THREAD_DONE = 2
    THREAD_ERROR = 3


class ThreadTypes(object):
    """
    Class for storing thread types.
    """

    START = 0
    MONITOR = 1
    COMMIT = 2

    names = {
        START: 'Start',
        MONITOR: 'Monitor',
        COMMIT: 'Commit',
    }


class JobMonitorCallback(monitor.JobLogDisplay):
    """
    Monitor job status changes.
    """

    monitorStates = (
        buildjob.JOB_STATE_STARTED,
        buildjob.JOB_STATE_BUILT,
        buildjob.JOB_STATE_FAILED,
        buildjob.JOB_STATE_COMMITTING,
        buildjob.JOB_STATE_COMMITTED,
    )

    def __init__(self, status, *args, **kwargs):
        # override showBuildLogs since we don't handle writing to the out pipe
        kwargs['showBuildLogs'] = False

        monitor.JobLogDisplay.__init__(self, *args, **kwargs)
        self._status = status

    def _msg(self, msg, *args):
        self._status.put((MessageTypes.LOG, msg))

    def _data(self, data):
        self._status.put((MessageTypes.DATA, data))

    def _jobStateUpdated(self, jobId, state, status):
        monitor.JobLogDisplay(self, jobId, state, None)
        if state in self.monitorStates:
            self._data((jobId, state))

    def _troveLogUpdated(self, (jobId, troveTuple), state, status):
        pass

    def _jobTrovesSet(self, jobId, troveData):
        pass

    def _tailBuildLog(self, jobId, troveTuple):
        pass

    def _primeOutput(self, jobId):
        # Override parents _primeOutput to avoid sending output to stdout via
        # print.
        logMark = 0
        while True:
            newLogs = self.client.getJobLogs(jobId, logMark)
            if not newLogs:
                break
            logMark += len(newLogs)
            for (timeStamp, message, args) in newLogs:
                self._msg('[%s] - %s' % (jobId, message))

        BUILDING = buildtrove.TROVE_STATE_BUILDING
        troveTups = self.client.listTrovesByState(jobId, BUILDING).get(BUILDING, [])
        for troveTuple in troveTups:
            self._tailBuildLog(jobId, troveTuple)

        monitor._AbstractDisplay._primeOutput(self, jobId)


class AbstractWorker(Thread):
    """
    Abstract class for all worker nodes.
    """

    threadType = None

    def __init__(self, status, name=None):
        Thread.__init__(self, name=name)

        self.status = status
        self.workerId = None

    def run(self):
        """
        Do work.
        """

        try:
            self.work()
        except Exception, e:
            self.status.put((MessageTypes.THREAD_ERROR,
                             (self.threadType, self.workerId, e)))

        self.status.put((MessageTypes.THREAD_DONE, self.workerId))

    def work(self):
        """
        Stub for sub classes to implement.
        """

        raise NotImplementedError


class StartWorker(AbstractWorker):
    """
    Worker thread for starting jobs and reporting status.
    """

    threadType = ThreadTypes.START

    def __init__(self, status, (builder, trove), name=None):
        AbstractWorker.__init__(self, status, name=name)

        self.builder = builder
        self.trove = trove
        self.workerId = self.trove

    def work(self):
        """
        Start the specified build and report jobId.
        """

        jobId = self.builder.start((self.trove, ))
        self.status.put((MessageTypes.DATA, (jobId, self.trove)))


class MonitorWorker(AbstractWorker):
    """
    Worker thread for monitoring jobs and reporting status.
    """

    threadType = ThreadTypes.MONITOR
    displayClass = JobMonitorCallback

    def __init__(self, status, (rmakeClient, jobId), name=None):
        AbstractWorker.__init__(self, status, name=name)

        self.client = rmakeClient
        self.jobId = jobId
        self.workerId = jobId

    def work(self):
        """
        Watch the monitor queue and monitor any available jobs.
        """

        # FIXME: This is copied from rmake.cmdlin.monitor for the most part
        #        because I need to pass extra args to the display class.

        uri, tmpPath = monitor._getUri(self.client)

        try:
            display = self.displayClass(self.status, self.client,
                                        showBuildLogs=False, exitOnFinish=True)
            client = self.client.listenToEvents(uri, self.jobId, display,
                                                showTroveDetails=False,
                                                serve=True)
            return client
        finally:
            if tmpPath:
                os.remove(tmpPath)


class CommitWorker(AbstractWorker):
    """
    Worker thread for committing jobs.
    """

    threadType = ThreadTypes.COMMIT

    def __init__(self, status, (builder, jobId), name=None):
        AbstractWorker.__init__(self, status, name=name)

        self.builder = builder
        self.jobId = jobId
        self.workerId = jobId

    def work(self):
        """
        Commit the specified job.
        """

        result = self.builder.commit(self.jobId)
        self.status.put((MessageTypes.DATA, (self.jobId, result)))


class AbstractStatusMonitor(object):
    """
    Abstract class for implementing monitoring classes.
    """

    workerClass = None

    def __init__(self, threadArgs):
        if type(threadArgs) not in (list, tuple, set):
            threadArgs = (threadArgs, )
        self._threadArgs = threadArgs

        self._status = Queue()
        self._workers = {}
        self._errors = []

    def addJob(self, job):
        """
        Add a job to the worker pool.
        """

        args = list(self._threadArgs)
        args.append(job)

        threadName = ('%s Worker'
            % ThreadTypes.names[self.workerClass.threadType])
        worker = self.workerClass(self._status, args, name=threadName)
        self._workers[job] = worker
        worker.daemon = True
        worker.start()

    def getStatus(self):
        """
        Process all messages in the status queue, returning any data messages.
        """

        data = []
        while True:
            try:
                msg = self._status.get_nowait()
            except Empty:
                break

            data.extend(self._processMessage(msg))

        return data

    def getErrors(self):
        """
        Return any errors found while status was being processed.
        """

        errors = self._errors
        self._errors = []
        return errors

    def _processMessage(self, msg):
        """
        Handle messages.
        """

        data = []
        mtype, payload = msg

        if mtype == MessageTypes.LOG:
            log.info(payload)
        elif mtype == MessageTypes.DATA:
            data.append(payload)
        elif mtype == MessageTypes.THREAD_DONE:
            job = payload
            #assert not self._workers[job].isAlive()
            del self._workers[job]
        elif mtype == MessageTypes.THREAD_ERROR:
            threadType, job, error = payload
            #assert not self._workers[job].isAlive()
            #raise error
            log.error('[%s] FAILED with exception: %s' % (job, error))
            self._errors.append((job, error))

        return data


class JobStarter(AbstractStatusMonitor):
    """
    Abstraction around threaded starter model.
    """

    workerClass = StartWorker
    startJob = AbstractStatusMonitor.addJob


class JobMonitor(AbstractStatusMonitor):
    """
    Abstraction around threaded monitoring model.
    """

    workerClass = MonitorWorker
    monitorJob = AbstractStatusMonitor.addJob


class JobCommitter(AbstractStatusMonitor):
    """
    Abstraction around threaded commit model.
    """

    workerClass = CommitWorker
    commitJob = AbstractStatusMonitor.addJob


class Dispatcher(object):
    """
    Manage building a list of troves in a way that doesn't bring rMake to its
    knees.
    """

    _completed = (
        -1, -2,
        buildjob.JOB_STATE_FAILED,
        buildjob.JOB_STATE_BUILT,
#        buildjob.JOB_STATE_COMMITTED
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
                self._jobs[jobId] = [trove, -1, None]
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
                if status in self._completed:
                    self._slots += 1
                    assert self._slots <= self._maxSlots

                # commit any jobs that are done building
                if status == buildjob.JOB_STATE_BUILT:
                    self._committer.commitJob(jobId)

            # check for commit status
            for jobId, result in self._committer.getStatus():
                self._jobs[jobId][2] = result

            # process monitor and commit errors
            for jobId, error in itertools.chain(self._monitor.getErrors(),
                                                self._committer.getErrors()):
                self._slots += 1
                self._jobs[jobId][1] = -2
                self._failures.append((jobId, error))

            # Wait for a bit before polling again.
            time.sleep(3)

        results = {}
        for jobId, (trove, status, result) in self._jobs.iteritems():
            # log failed jobs
            if status == buildjob.JOB_STATE_FAILED:
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
