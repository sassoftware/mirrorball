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
