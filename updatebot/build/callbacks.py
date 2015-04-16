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


from rmake.build import buildjob
from rmake.build import buildtrove
from rmake.cmdline import monitor

from updatebot.build.constants import MessageTypes

class StatusOnlyDisplay(monitor.JobLogDisplay):
    """
    Display only job and trove status. No log output.

    Copied from bob3
    """

    # R0901 - Too many ancestors
    # pylint: disable=R0901

    def _troveLogUpdated(self, (jobId, troveTuple), state, status):
        """
        Don't care about trove logs
        """

    def _trovePreparingChroot(self, (jobId, troveTuple), host, path):
        """
        Don't care about resolving/installing chroot
        """

    def _tailBuildLog(self, jobId, troveTuple):
        """
        Don't care about the build log
        """

    def _stopTailing(self, jobId, troveTuple):
        """
        Don't care about the build log
        """


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

    doneStates = (
        buildjob.JOB_STATE_FAILED,
        buildjob.JOB_STATE_COMMITTED,
    )

    def __init__(self, status, *args, **kwargs):
        # override showBuildLogs since we don't handle writing to the out pipe
        kwargs['showBuildLogs'] = False

        monitor.JobLogDisplay.__init__(self, *args, **kwargs)
        self._status = status
        self._states = []

    def _msg(self, msg, *args):
        self._status.put((MessageTypes.LOG, msg))

    def _data(self, data):
        self._status.put((MessageTypes.DATA, data))

    def _jobStateUpdated(self, jobId, state, status):
        monitor.JobLogDisplay._jobStateUpdated(self, jobId, state, None)
        if state in self._states:
            return
        self._states.append(state)
        if state in self.monitorStates:
            self._data((jobId, state))
        if state in self.doneStates:
            self.finished = True

    def _troveLogUpdated(self, (jobId, troveTuple), state, status):
        pass

    def _jobTrovesSet(self, jobId, troveData):
        pass

    def _tailBuildLog(self, jobId, troveTuple):
        pass

    def _serveLoopHook(self):
        pass

    def _setFinished(self):
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
