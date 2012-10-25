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
