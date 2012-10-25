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
    # pylint: disable-msg=R0901

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
