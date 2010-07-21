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

    names = {
        START: 'Start',
        MONITOR: 'Monitor',
        COMMIT: 'Commit',
        LOCAL_GROUP_BUILD: 'Local Group Build',
        LOCAL_CHANGESET_COMMIT: 'Local Changeset Commit',
        REBUILD_START: 'Rebuild Start',
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
