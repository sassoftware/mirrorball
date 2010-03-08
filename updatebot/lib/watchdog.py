#
# Copyright (c) 2010 rPath, Inc.
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
