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
Module for common abstract classes.
"""

import logging
from Queue import Queue
from Queue import Empty
from threading import Thread

from updatebot.build.constants import ThreadTypes
from updatebot.build.constants import MessageTypes

log = logging.getLogger('updatebot.build')

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
