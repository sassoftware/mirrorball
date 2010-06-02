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
Module for managing monitors.
"""

import os

from rmake.cmdline import monitor

from updatebot.build.common import AbstractWorker
from updatebot.build.common import AbstractStatusMonitor

from updatebot.build.constants import ThreadTypes
from updatebot.build.constants import MessageTypes
from updatebot.build.callbacks import JobMonitorCallback

class StartWorker(AbstractWorker):
    """
    Worker thread for starting jobs and reporting status.
    """

    threadType = ThreadTypes.START

    def __init__(self, status, (builder, trove)):
        AbstractWorker.__init__(self, status)

        self.builder = builder
        self.trove = trove
        self.workerId = self.trove

    def work(self):
        """
        Start the specified build and report jobId.
        """

        jobId = self.builder.start(self.trove)
        self.status.put((MessageTypes.DATA, (jobId, self.trove)))


class MonitorWorker(AbstractWorker):
    """
    Worker thread for monitoring jobs and reporting status.
    """

    threadType = ThreadTypes.MONITOR
    displayClass = JobMonitorCallback

    def __init__(self, status, (rmakeClient, jobId)):
        AbstractWorker.__init__(self, status)

        self.client = rmakeClient
        self.jobId = jobId
        self.workerId = jobId

    def work(self):
        """
        Watch the monitor queue and monitor any available jobs.
        """

        # FIXME: This is copied from rmake.cmdline.monitor for the most part
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

    def __init__(self, status, (builder, jobId)):
        AbstractWorker.__init__(self, status)

        self.builder = builder
        self.jobId = jobId
        self.workerId = jobId

    def work(self):
        """
        Commit the specified job.
        """

        result = self.builder.commit(self.jobId)
        self.status.put((MessageTypes.DATA, (self.jobId, result)))


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
