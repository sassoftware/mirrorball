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
Module for common abstract classes.
"""

import logging
from Queue import Empty
from Queue import Queue
from threading import Thread

from multiprocessing import Process
from multiprocessing.queues import Queue as ProcessQueue

from updatebot.lib import util
from updatebot.build.constants import MessageTypes

log = logging.getLogger('updatebot.build')

class LogQueue(object):
    def __init__(self, logger):
        self._log = logger
        self._prefix = None

    def setPrefix(self, prefix):
        self._prefix = prefix

    def log(self, level, msg):
        if self._prefix:
            msg = self._prefix + msg
        self._log.put((MessageTypes.LOG, msg))

    def info(self, msg):
        self.log(logging.INFO, msg)

    def warn(self, msg):
        self.log(logging.WARNING, msg)

    def critical(self, msg):
        self.log(logging.CRITICAL, msg)

    def error(self, msg):
        self.log(logging.ERROR, msg)


class AbstractWorker(object):
    """
    Abstract class for all worker nodes.
    """

    threadType = None

    def __init__(self, status):
        self.status = status
        self.workerId = None
        self.log = LogQueue(status)

    def run(self):
        """
        Do work.
        """

        try:
            self.work()
        except Exception, e:
            self.status.put((MessageTypes.THREAD_ERROR,
                             (self.threadType, self.workerId, str(e))))

        self.status.put((MessageTypes.THREAD_DONE, self.workerId))

    def work(self):
        """
        Stub for sub classes to implement.
        """

        raise NotImplementedError


class AbstractWorkerThread(AbstractWorker, Thread):
    """
    Abstract class for worker threads.
    """

    queueClass = Queue

    def __init__(self, status):
        AbstractWorker.__init__(self, status)
        Thread.__init__(self)


class AbstractWorkerProcess(AbstractWorker, Process):
    """
    Abstract class for worker processes.
    """

    queueClass = ProcessQueue

    def __init__(self, status):
        AbstractWorker.__init__(self, status)
        Process.__init__(self)
        self.processId = '[none set]'
        self.daemon = True

    def run(self):
        util.setproctitle(self.processId)
        self.log.setPrefix('[%s] ' % self.pid)
        self.log.info('starting %s' % self.processId)
        AbstractWorker.run(self)
        self.status.close()
        self.status.join_thread()


class AbstractStatusMonitor(object):
    """
    Abstract class for implementing monitoring classes.
    """

    workerClass = None

    def __init__(self, threadArgs, retries=0):
        if type(threadArgs) not in (list, tuple, set):
            threadArgs = (threadArgs, )
        self._threadArgs = threadArgs

        self._status = self.workerClass.queueClass()
        self._workers = {}
        self._errors = []

        self._retries = Retries(retries)

    def addJob(self, job):
        """
        Add a job to the worker pool.
        """

        # Make sure job is hashable.
        if isinstance(job, list):
            job = tuple(job)
        elif isinstance(job, set):
            job = frozenset(job)

        args = list(self._threadArgs)
        args.append(job)

        worker = self.workerClass(self._status, args)

        if worker.workerId in self._workers:
            log.critical('job already being monitored: %s' % (job, ))
            import epdb; epdb.st()
            return

        self._workers[worker.workerId] = worker
        self._retries.addJob(worker.workerId)
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
                # DEBUG
                log.debug('I got this from _status.get_nowait() %s' % str(msg))
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
        # DEBUG

        log.debug('mtype is %s' % str(mtype))
        if mtype == MessageTypes.LOG:
            # mtype == 0 in this situation
            #log.info('MessageTypes.LOG')
            log.info(payload)
        elif mtype == MessageTypes.DATA:
            # mytpe == 1 in this situation
            log.info('DATA recieved: %s ' % str(payload))
            data.append(payload)
        elif mtype == MessageTypes.THREAD_DONE:
            # mtype == 2 in this situation
            log.debug('Job done -- I should delete the worker')
            log.info('Job done payload is %s' % str(payload))
            job = payload
            #assert not self._workers[job].isAlive()
            if job in self._workers:
                log.debug('Worker I am looking to del %s' % str(self._workers[job]))
                log.debug('WORKERS: %s' % str(self._workers))
                del self._workers[job]
            else:
                log.critical('JOB NOT FOUND %s' % (job, ))
        elif mtype == MessageTypes.THREAD_ERROR:
            threadType, job, error = payload
            #assert not self._workers[job].isAlive()
            #raise error
            log.error('[%s] FAILED with exception: %s' % (job, error))

            workerId = self._workers[job].workerId
            if self._retries.retry(workerId):
                log.info('retrying %s' % (job, ))
                self._workers.pop(job, None)
                self.addJob(workerId)
            else:
                self._errors.append((job, error))

        return data


class Retries(object):
    def __init__(self, retries):
        self.retries = retries
        self._jobs = {}

    def addJob(self, jobId):
        if jobId not in self._jobs:
            self._jobs[jobId] = 0

    def retry(self, jobId):
        if self._jobs[jobId] + 1 > self.retries:
            return False
        self._jobs[jobId] += 1
