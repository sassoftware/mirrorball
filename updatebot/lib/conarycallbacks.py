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
Conary callbacks that have been wrapped to be more friendly with the
logging module.
"""

import logging
log = logging.getLogger('updatebot.lib.conarycallbacks')

from conary.build.cook import CookCallback
from conary.conaryclient.callbacks import CloneCallback

def callonce(func):
    def wrapper(self, *args, **kwargs):
        if self._last != func.__name__:
            self._last = func.__name__
            return func(self, *args, **kwargs)
    return wrapper

class BaseCallback(object):
    def __init__(self, *args, **kwargs):
        self._last = None

    def _message(self, message):
        self._log.info(message)

class UpdateBotCloneCallback(BaseCallback, CloneCallback):
    def __init__(self, *args, **kwargs):
        self._log = kwargs.pop('log', log)
        BaseCallback.__init__(self, *args, **kwargs)
        CloneCallback.__init__(self, *args, **kwargs)

    @callonce
    def determiningCloneTroves(self, current=0, total=0):
        CloneCallback.determiningCloneTroves(self, current=0, total=0)

    @callonce
    def determiningTargets(self):
        CloneCallback.determiningTargets(self)

    @callonce
    def targetSources(self, current=0, total=0):
        CloneCallback.targetSources(self, current=0, total=0)

    @callonce
    def targetBinaries(self, current=0, total=0):
        CloneCallback.targetBinaries(self, current=0, total=0)

    @callonce
    def checkNeedsFulfilled(self, current=0, total=0):
        CloneCallback.checkNeedsFulfilled(self, current=0, total=0)

    @callonce
    def rewriteTrove(self, current=0, total=0):
        CloneCallback.rewriteTrove(self, current=0, total=0)

    @callonce
    def buildingChangeset(self, current=0, total=0):
        CloneCallback.buildingChangeset(self, current=0, total=0)

    @callonce
    def requestingFiles(self, number):
        CloneCallback.requestingFiles(self, number)

    @callonce
    def requestingFileContentsWithCount(self, count):
        CloneCallback.requestingFileContentsWithCount(self, count)

    @callonce
    def gettingCloneData(self):
        CloneCallback.gettingCloneData(self)

    @callonce
    def sendingChangset(self, got, need):
        self._message('uploading changeset')

class UpdateBotCookCallback(BaseCallback, CookCallback):
    def __init__(self, *args, **kwargs):
        self._log = kwargs.pop('log', log)
        BaseCallback.__init__(self, *args, **kwargs)
        CookCallback.__init__(self, *args, **kwargs)
