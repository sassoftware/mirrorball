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
Module of logging related functions.
"""

import sys
import time
import logging
import tempfile
from logging import handlers

def addRootLogger(logFile=None):
    """
    Setup the root logger that should be inherited by all other loggers.
    """

    logSize = 1024 * 1024 * 50
    logFile = logFile and logFile or tempfile.mktemp(prefix='updatebot-log-%s-'
                                                            % int(time.time()))

    rootLog = logging.getLogger('')

    streamHandler = logging.StreamHandler(sys.stderr)
    logFileHandler = handlers.RotatingFileHandler(logFile,
                                                  maxBytes=logSize,
                                                  backupCount=5)

    streamFormatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
    fileFormatter = logging.Formatter('%(asctime)s %(levelname)s '
        '%(name)s %(message)s')

    streamHandler.setFormatter(streamFormatter)
    logFileHandler.setFormatter(fileFormatter)

    rootLog.addHandler(streamHandler)
    rootLog.addHandler(logFileHandler)

    rootLog.setLevel(logging.INFO)

    # Delete conary's log handler since it puts things on stderr and without
    # any timestamps.
    conaryLog = logging.getLogger('conary')
    for handler in conaryLog.handlers:
        conaryLog.removeHandler(handler)

    return rootLog
