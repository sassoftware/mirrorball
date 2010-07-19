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
Module for cordinating local group builds.
"""

from updatebot.lib import conarycallbacks
from updatebot.build.constants import WorkerTypes
from updatebot.build.constants import MessageTypes
from updatebot.build.common import AbstractStatusMonitor
from updatebot.build.common import AbstractWorkerProcess as AbstractWorker

class LocalGroupCookWorker(AbstractWorker):
    """
    Worker process for doing local cooks of groups.
    """

    threadType = WorkerTypes.LOCAL_GROUP_BUILD

    def __init__(self, status, (builder, (trove, flavorFilter))):
        AbstractWorker.__init__(self, status)

        self.builder = builder
        self.trove = trove
        self.workerId = trove
        self.processId = 'cook %s=%s' % (trove[0], trove[1])
        self.flavorFilter = flavorFilter

    def work(self):
        """
        Build the specified trove and commit it to the repository.
        """

        res, csfn = self.builder.cvc.cook(self.trove,
            flavorFilter=self.flavorFilter, commit=False,
            callback=conarycallbacks.UpdateBotCookCallback(log=self.log))
        self.status.put((MessageTypes.DATA, (self.trove, res, csfn)))


class LocalChangeSetCommitWorker(AbstractWorker):
    """
    Worker process for doing local changeset commits.
    """

    threadType = WorkerTypes.LOCAL_CHANGESET_COMMIT

    def __init__(self, status, (builder, (trove, csfn))):
        AbstractWorker.__init__(self, status)

        self.builder = builder
        self.csfn = csfn
        self.trove = trove
        self.workerId = trove
        self.processId = 'commit %s=%s' % (trove[0], trove[1])

    def work(self):
        """
        Commit the specified changeset.
        """

        results = self.builder.cvc.commitChangeSetFile(self.csfn,
            callback=conarycallbacks.UpdateBotCookCallback(log=self.log))
        self.status.put((MessageTypes.DATA, (self.trove, results)))


class LocalGroupCooker(AbstractStatusMonitor):
    """
    Class for managing group workers.
    """

    workerClass = LocalGroupCookWorker
    buildGroup = AbstractStatusMonitor.addJob


class LocalChangeSetCommitter(AbstractStatusMonitor):
    """
    Class for managing commit workers.
    """

    workerClass = LocalChangeSetCommitWorker
    commitChangeSet = AbstractStatusMonitor.addJob

