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
