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
import itertools

from rmake.cmdline import monitor

from updatebot.build.common import AbstractStatusMonitor
from updatebot.build.common import AbstractWorkerThread as AbstractWorker

from updatebot.build.constants import WorkerTypes
from updatebot.build.constants import MessageTypes
from updatebot.build.callbacks import JobMonitorCallback

class StartWorker(AbstractWorker):
    """
    Worker thread for starting jobs and reporting status.
    """

    threadType = WorkerTypes.START

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
        self.status.put((MessageTypes.DATA, (self.trove, jobId)))


class RebuildStartWorker(StartWorker):
    """
    Worker thread for starting package rebuild jobs and reporting status.
    """

    threadType = WorkerTypes.REBUILD_START

    def __init__(self, status, (builder, useLatest,
        additionalResolveTroves, trove)):
        StartWorker.__init__(self, status, (builder, trove))

        self.useLatest = useLatest
        self.additionalResolveTroves = additionalResolveTroves

    def work(self):
        """
        Start the specified build and report jobId.
        """

        jobIds = self.builder.rebuild(self.trove, useLatest=self.useLatest,
            additionalResolveTroves=self.additionalResolveTroves, commit=False)

        if len(jobIds) != 1:
            self.status.put((MessageTypes.THREAD_ERROR, (self.threadType,
                self.workerId, 'More jobIds returned than expected while '
                'building %s' % self.trove)))
        else:
            self.status.put((MessageTypes.DATA, (self.trove, jobIds[0])))


class MonitorWorker(AbstractWorker):
    """
    Worker thread for monitoring jobs and reporting status.
    """

    threadType = WorkerTypes.MONITOR
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

    threadType = WorkerTypes.COMMIT

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


class PromoteWorker(AbstractWorker):
    """
    Worker thread for promoting committed troves.
    """

    threadType = WorkerTypes.PROMOTE

    def __init__(self, status, (helper, targetLabel, jobs)):
        AbstractWorker.__init__(self, status)

        self.helper = helper
        self.targetLabel = targetLabel
        self.jobs = jobs
        self.workerId = (x[0] for x in jobs)

    def work(self):
        """
        Promote the specified list of troves.
        """

        # Let's be smart about promoting troves and batch all of the jobs
        # together. This means we need to keep track of what we put in and
        # what we get back so that we can map the output to a jobId.

        # Build mapping of nvf tuple to jobId
        jobMap = {}
        for jobId, built in self.jobs:
            for srcTrv, binTrvs in dict(built).iteritems():
                for binTrv in binTrvs:
                    jobMap.setdefault(binTrv, list()).append(jobId, srcTrv)

        # Get the list of binary troves to promote.
        trvLst = jobMap.keys()

        # Assume that all troves are on the same source label.
        srcLabel = trvLst[0][1].trailingLabel()

        # Promote
        result = self.helper.promote(trvLst, set(), srcLabel, self.targetLabel,
            checkPackageList=False)

        # Map the results back to source label troves
        clonedFrom = self.helper.getClonedFrom(result)

        # Map jobIds back to promoted troves.
        resultMap = {}
        for spec, (jobId, srcTrv) in jobMap.iteritems():
            resultMap.setdefault(jobId, dict()).setdefault(srcTrv,
                set()).add(clonedFrom.get(spec))

        # Send back all of the results.
        self.status.put((MessageTypes.DATA, tuple(resultMap.items())))


class JobStarter(AbstractStatusMonitor):
    """
    Abstraction around threaded starter model.
    """

    workerClass = StartWorker
    startJob = AbstractStatusMonitor.addJob


class JobRebuildStarter(AbstractStatusMonitor):
    """
    Abstraction around threaded rebuild starter model.
    """

    workerClass = RebuildStartWorker
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


class JobPromoter(AbstractStatusMonitor):
    """
    Abstraction around threaded promote model.
    """

    workerClass = PromoteWorker
    promoteJob = AbstractStatusMonitor.addJob
