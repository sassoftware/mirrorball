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
