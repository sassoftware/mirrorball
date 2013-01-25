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
Common module between all pkgSource implementations.
"""

import copy
import logging

log = logging.getLogger('updatebot.pkgsource')

class BasePackageSource(object):
    """
    Base class for pkgSources
    """

    def __init__(self, cfg, ui):
        self._cfg = cfg
        self._ui = ui

        self._excludeArch = self._cfg.excludeArch

        self._loaded = False

        # {repoShortUrl: clientObj}
        self._clients = dict()

        # {location: srpm}
        self.locationMap = dict()

        # {srcPkg: [binPkg, ... ] }
        self.srcPkgMap = dict()

        # {binPkg: srcPkg}
        self.binPkgMap = dict()

        # {srcName: [srcPkg, ... ] }
        self.srcNameMap = dict()

        # {binName: [binPkg, ... ] }
        self.binNameMap = dict()

        # {binPkg: set(binNames) }
        self.obsoletesMap = dict()

        # {(binName, srcConaryVersion, archStr): [archStr, archStr, ...]}
        self.useMap = dict()

    def __copy__(self):
        log.info('copying pkgsource')
        cls = self.__class__
        obj = cls(self._cfg, self._ui)
        obj.locationMap = copy.copy(self.locationMap)
        obj.srcPkgMap = copy.copy(self.srcPkgMap)
        obj.binPkgMap = copy.copy(self.binPkgMap)
        obj.srcNameMap = copy.copy(self.srcNameMap)
        obj.binNameMap = copy.copy(self.binNameMap)
        obj.useMap = copy.copy(self.useMap)
        return obj

    def __deepcopy__(self, memo):
        log.info('deepcopying pkgsource')
        cls = self.__class__
        obj = cls(self._cfg, self._ui)
        obj.locationMap = copy.deepcopy(self.locationMap, memo)
        obj.srcPkgMap = copy.deepcopy(self.srcPkgMap, memo)
        obj.binPkgMap = copy.deepcopy(self.binPkgMap, memo)
        obj.srcNameMap = copy.deepcopy(self.srcNameMap, memo)
        obj.binNameMap = copy.deepcopy(self.binNameMap, memo)
        obj.useMap = copy.deepcopy(self.useMap, memo)
        return obj

    def getClients(self):
        """
        Get instances of repository clients.
        """

        if not self._clients:
            self.load()

        return self._clients

    def load(self):
        """
        Method to parse all package data into data structures listed above.
        NOTE: This method should be implmented by all backends.
        """
