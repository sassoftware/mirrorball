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

    MONITOR = 0
    COMMIT = 1

    names = {
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


class MonitorWorker(Thread):
    """
    Worker thread for monitoring jobs and reporting status.
    """

    threadType = ThreadTypes.MONITOR
    displayClass = JobMonitorCallback

    def __init__(self, jobId, status, rmakeClient, name=None):
        Thread.__init__(self, name=name)

        self.setDaemon(False)

        self.client = rmakeClient
        self.jobId = jobId
        self.status = status
        self.name = name

    def run(self):
        """
        Watch the monitor queue and monitor any available jobs.
        """

        # monitor job, job display class supplies status information back to
        # the main thread via the status queue.
        try:
            self.monitorJob(self.jobId)
        except Exception, e:
            self.status.put((MessageTypes.THREAD_ERROR,
                             (ThreadType.MONITOR, self.jobId, e)))

        self.status.put((MessageTypes.THREAD_DONE, self.jobId))

    def monitorJob(self, jobId):
        """
        Monitor the specified job.
        """

        # FIXME: This is copied from rmake.cmdlin.monitor for the most part
        #        because I need to pass extra args to the display class.

        uri, tmpPath = monitor._getUri(self.client)

        try:
            display = self.displayClass(self.status, self.client,
                                        showBuildLogs=False, exitOnFinish=True)
            client = self.client.listenToEvents(uri, jobId, display,
                                                showTroveDetails=False,
                                                serve=True)
            return client
        finally:
            if tmpPath:
                os.remove(tmpPath)


class CommitWorker(Thread):
    """
    Worker thread for committing jobs.
    """

    threadType = ThreadTypes.COMMIT

    def __init__(self, jobId, status, builder, name=None):
        Thread.__init__(self, name=name)

        self.builder = builder
        self.jobId = jobId
        self.status = status
        self.name = name

    def run(self):
        """
        Commit the specified job.
        """

        try:
            result = self.builder.commit(self.jobId)
            self.status.put((MessageTypes.DATA, (self.jobId, result)))
        except Exception, e:
            self.status.put((MessageTypes.THREAD_ERROR,
                             (ThreadType.COMMIT, self.jobId, e)))

        self.status.put((MessageTypes.THREAD_DONE, self.jobId))


class AbstractStatusMonitor(object):
    """
    Abstract class for implementing monitoring classes.
    """

    workerClass = None

    def __init__(self, threadArgs):
        self._threadArgs = threadArgs

        self._status = Queue()
        self._workers = {}

    def addJobId(self, jobId):
        """
        Add a jobId to the worker pool.
        """

        threadName = ('%s Worker'
            % ThreadTypes.names[self.workerClass.threadType])
        worker = self.workerClass(jobId, self._status, *self._threadArgs,
                                  name=threadName)
        self._workers[jobId] = worker
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
            jobId = payload
            assert not self._workers[jobId].isAlive()
            del self._workers[jobId]
        elif mtype == MessageTypes.THREAD_ERROR:
            threadType, jobId, error = payload
            assert not self._workers[jobId].isAlive()
            raise error

        return data


class JobMonitor(AbstractStatusMonitor):
    """
    Abstraction around threaded monitoring model.
    """

    workerClass = MonitorWorker
    monitorJob = AbstractStatusMonitor.addJobId


class JobCommitter(AbstractStatusMonitor):
    """
    Abstraction around threaded commit model.
    """

    workerClass = CommitWorker
    commitJob = AbstractStatusMonitor.addJobId


class Dispatcher(object):
    """
    Manage building a list of troves in a way that doesn't bring rMake to its
    knees.
    """

    _completed = (buildjob.JOB_STATE_FAILED,
                  buildjob.JOB_STATE_COMMITTED)

    def __init__(self, builder, maxSlots):
        self._builder = builder
        self._maxSlots = maxSlots
        self._slots = maxSlots

        self._monitor = JobMonitor((self._builder._helper.client, ))
        self._committer = JobCommitter((self._builder, ))

        # jobId: (trv, status, commitData)
        self._jobs = {}

    def buildmany(self, troveSpecs):
        """
        Build as many packages as possible until we run out of slots.
        """

        troves = list(troveSpecs)
        troves.reverse()

        while troves or not self._jobDone():
            # fill slots with available troves
            while troves and self._slots:
                # get trove to work on
                trove = troves.pop()

                # start build job
                jobId = self._builder.start((trove, ))
                self._jobs[jobId] = [trove, -1, None]
                self._slots -= 1
                self._monitor.monitorJob(jobId)

            # update job status changes
            for jobId, status in self._monitor.getStatus():
                self._jobs[jobId][1] = status
                if status in self._completed:
                    self._slots += 1
                    assert self._slots <= self._maxSlots

                # commit any jobs that are complete
                if status == buildjob.JOB_STATE_BUILT:
                    self._committer.commitJob(jobId)

            # check for commit status
            for jobId, result in self._committer.getStatus():
                self._jobs[jobId][2] = result

        results = {}
        for jobId, (trove, status, result) in self._jobs.iteritems():
            # log failed jobs
            if status == buildjob.JOB_STATE_FAILED:
                log.info('[%s] failed job: %s' % (jobId, trove))
            else:
                results[trove] = result

        return results

    def _jobDone(self):
        for jobId, (trove, status, result) in self._jobs.iteritems():
            if status not in self._completed:
                return False
        return True
