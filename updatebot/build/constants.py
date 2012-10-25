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
Build system contants.
"""

class MessageTypes(object):
    """
    Class for storing message type constants.
    """

    LOG = 0
    DATA = 1
    THREAD_DONE = 2
    THREAD_ERROR = 3


class WorkerTypes(object):
    """
    Class for storing thread types.
    """

    START = 0
    MONITOR = 1
    COMMIT = 2
    LOCAL_GROUP_BUILD = 3
    LOCAL_CHANGESET_COMMIT = 4
    REBUILD_START = 5
    PROMOTE = 6

    names = {
        START: 'Start',
        MONITOR: 'Monitor',
        COMMIT: 'Commit',
        LOCAL_GROUP_BUILD: 'Local Group Build',
        LOCAL_CHANGESET_COMMIT: 'Local Changeset Commit',
        REBUILD_START: 'Rebuild Start',
        PROMOTE: 'Promote Troves',
    }


class JobStatus(object):
    """
    Job states in dispatcher.
    """

    JOB_NOT_STARTED = -1
    ERROR_MONITOR_FAILURE = -2
    ERROR_COMMITTER_FAILURE = -3
    JOB_COMMITTING = -4
    JOB_BUILDING = -5
    JOB_BUILT = -6
    JOB_COMMITTED = -7
    JOB_FAILED = -8
    JOB_STARTING = -9
    JOB_PROMOTING = -10
    JOB_PROMOTED = -11
    ERROR_PROMOTE_FAILURE = -12
