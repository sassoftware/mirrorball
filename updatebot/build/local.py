#
# Copyright (c) rPath, Inc.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
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
