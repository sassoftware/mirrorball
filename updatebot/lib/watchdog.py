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
Watch and wait for processes to fail and then restart them.
"""

import os
import logging

log = logging.getLogger('updatebot.lib.watchdog')

def runOnce(func, *args, **kwargs):
    """
    Fork and run a function.
    """

    pid = os.fork()
    if not pid:
        log.info('started %s(pid %s)' % (func.__name__, os.getpid()))
        rc = func(*args, **kwargs)
        os._exit(rc)
    else:
        return pid

def waitOnce(func, *args, **kwargs):
    """
    Fork and wait for a function to complete.
    """

    pid = runOnce(func, *args, **kwargs)

    log.info('waiting for %s' % pid)
    pid, status = os.waitpid(pid, 0)
    if os.WIFEXITED(status):
        rc = os.WEXITSTATUS(status)
        return rc

def loopwait(func, *args, **kwargs):
    """
    Run a forked function in a loop.
    """

    while True:
        log.info('looping %s' % func.__name__)
        rc = waitOnce(func, *args, **kwargs)
        if not rc:
            log.info('completed function loop')
            break

    return rc

def forknloop(func):
    """
    Decorator to run a function in a forked process in a loop.
    """

    def wrapper(*args, **kwargs):
        return loopwait(func, *args, **kwargs)
    return wrapper

def forknwait(func):
    """
    Decorator to run a function in a forked process and wait for it to complete.
    """

    def wrapper(*args, **kwargs):
        return waitOnce(func, *args, **kwargs)
    return wrapper
