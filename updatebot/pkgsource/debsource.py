#
# Copyright (c) 2008 rPath, Inc.
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

import logging

import aptmd
from updatebot import util

class DebSource(object):
    def __init__(self, cfg):
        self._excludeArch = cfg.excludeArch

        self._binPkgs = set()
        self._srcPkgs = set()

        self.srcPkgMap = dict()
        self.binPkgMap = dict()
        self.srcNameMap = dict()
        self.binNameMap = dict()
        self.locationMap = dict()

    def loadFromClient(self, client, path):
        for pkg in self.client.parse(path):
            if pkg.arch in self._excludeArch:
                continue

            if pkg.arch == 'src':
                self._procSrc(pkg)
            else:
                self._procBin(pkg)

    def _procSrc(self, pkg):
        if pkg.name not in self.srcNameMap:
            self.srcNameMap[pkg.name] = set()
        self.srcNameMap[pkg.name].add(pkg)

        for location in pkg.files:
            self.locationMap[location] = pkg

        self._srcPkgs.add(pkg)

    def _procBin(self, pkg):
        if pkg.name not in self.binNameMap:
            self.binNameMap[pkg.name] = set()
        self.binNameMap[pkg.name].add(pkg)

        self.locationMap[pkg.location] = pkg

        self._binPkgs.add(pkg)

    def finalize(self):
        for srcPkg in self._srcPkgs:
            if srcPkg in self.srcPkgMap:
                continue

            self.srcPkgMap[srcPkg] = set()
            for binPkgName in srcPkg.binaries:
                for binPkg in self.binNameMap[binPkgName]:
                    if binPkg.version == srcPkg.version and binPkg.release == srcPkg.release:
                        self.srcPkgMap[srcPkg].add(binPkg)
            self.srcPkgMap[srcPkg].add(srcPkg)

        for pkg in self.srcPkgMap[srcPkg]:
            self.binPkgMap[pkg] = srcPkg
