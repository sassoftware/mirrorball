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
