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

def runOnce(func, funcArgs):
    """
    Fork and run a function.
    """

    pid = os.fork()
    if not pid:
        log.info('started %s(pid %s)' % (func.__name__, os.getpid()))
        args, kwargs = funcArgs
        rc = func(*args, **kwargs)
        os._exit(rc)
    else:
        return pid

def watchOnce(func, funcArgs):
    """
    Fork and wait for a function to complete.
    """

    pid = runOnce(func, funcArgs)

    log.info('waiting for %s' % pid)
    pid, status = os.waitpid(pid, 0)
    if os.WIFEXITED(status):
        rc = os.WEXITSTATUS(status)
        return rc

def watch(func, funcArgs):
    """
    Run a forked function in a loop.
    """

    while True:
        log.info('looping %s' % func.__name__)
        rc = watchOnce(func, funcArgs)
        if not rc:
            log.info('completed function loop')
            break

    return rc

def forknwatch(func):
    """
    Decorator to run a function in a forked process in a loop.
    """

    def wrapper(*args, **kwargs):
        funcArgs = (args, kwargs)
        return watch(func, funcArgs)
    return wrapper
