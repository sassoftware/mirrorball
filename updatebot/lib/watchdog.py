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
