#
# Copyright (c) 2008-2010 rPath, Inc.
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
Common module between all pkgSource implementations.
"""

import copy
import logging

log = logging.getLogger('updatebot.pkgsource')

class BasePackageSource(object):
    """
    Base class for pkgSources
    """

    def __init__(self, cfg):
        self._cfg = cfg
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

    def __copy__(self):
        log.info('copying pkgsource')
        cls = self.__class__
        obj = cls(self._cfg)
        obj.locationMap = copy.copy(self.locationMap)
        obj.srcPkgMap = copy.copy(self.srcPkgMap)
        obj.binPkgMap = copy.copy(self.binPkgMap)
        obj.srcNameMap = copy.copy(self.srcNameMap)
        obj.binNameMap = copy.copy(self.binNameMap)
        return obj

    def __deepcopy__(self, memo):
        log.info('deepcopying pkgsource')
        cls = self.__class__
        obj = cls(self._cfg)
        obj.locationMap = copy.deepcopy(self.locationMap, memo)
        obj.srcPkgMap = copy.deepcopy(self.srcPkgMap, memo)
        obj.binPkgMap = copy.deepcopy(self.binPkgMap, memo)
        obj.srcNameMap = copy.deepcopy(self.srcNameMap, memo)
        obj.binNameMap = copy.deepcopy(self.binNameMap, memo)
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
