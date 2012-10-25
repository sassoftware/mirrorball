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

    @callonce
    def downloadingChangeSet(self, got, need):
        self._message('Downloading changeset')


class UpdateBotCookCallback(BaseCallback, CookCallback):
    def __init__(self, *args, **kwargs):
        self._log = kwargs.pop('log', log)
        BaseCallback.__init__(self, *args, **kwargs)
        CookCallback.__init__(self, *args, **kwargs)

    @callonce
    def sendingChangset(self, got, need):
        self._message('Committing changeset')

    @callonce
    def downloadingChangeSet(self, got, need):
        self._message('Downloading changeset')
