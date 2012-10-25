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
Package source for APT repositories.
"""

import logging

import aptmd
from updatebot.pkgsource.common import BasePackageSource

log = logging.getLogger('updatebot.pkgsource')

class DebSource(BasePackageSource):
    """
    PackageSource backend for APT repositories.
    """

    def __init__(self, cfg, ui):
        BasePackageSource.__init__(self, cfg, ui)

        self._binPkgs = set()
        self._srcPkgs = set()

    def load(self):
        """
        Load repository metadata from a config object.
        """

        if self._loaded:
            return

        client = aptmd.Client(self._cfg.repositoryUrl)
        for repo in self._cfg.repositoryPaths:
            log.info('loading repository data %s' % repo)
            self.loadFromClient(client, repo)
            self._clients[repo] = client

        self.finalize()
        self._loaded = True

    def loadFromClient(self, client, path):
        """
        Load repository metadata from a aptmd client object.
        """

        for pkg in client.parse(path):
            if pkg.arch in self._excludeArch:
                continue

            if pkg.arch == 'src':
                self._procSrc(pkg)
            else:
                self._procBin(pkg)

    def _procSrc(self, pkg):
        """
        Process source packages.
        """

        if pkg.name not in self.srcNameMap:
            self.srcNameMap[pkg.name] = set()
        self.srcNameMap[pkg.name].add(pkg)

        for location in pkg.files:
            self.locationMap[location] = pkg

        self._srcPkgs.add(pkg)

    def _procBin(self, pkg):
        """
        Process binary packages.
        """

        if pkg.name not in self.binNameMap:
            self.binNameMap[pkg.name] = set()
        self.binNameMap[pkg.name].add(pkg)

        self.locationMap[pkg.location] = pkg

        self._binPkgs.add(pkg)

    def finalize(self):
        """
        Finalize all data structures.
        """

        for srcPkg in self._srcPkgs:
            if srcPkg in self.srcPkgMap:
                continue

            self.srcPkgMap[srcPkg] = set()
            for binPkgName in srcPkg.binaries:
                if binPkgName not in self.binNameMap:
                    # This means that we don't have a binary package that was
                    # built with srcPkg, but that is ok.
                    continue

                for binPkg in self.binNameMap[binPkgName]:
                    if ((binPkg.version == srcPkg.version and
                         binPkg.release == srcPkg.release) or
                        (binPkg.source == srcPkg.name and
                         binPkg.sourceVersion == srcPkg.version)):
                        self.srcPkgMap[srcPkg].add(binPkg)

            self.srcPkgMap[srcPkg].add(srcPkg)

            for pkg in self.srcPkgMap[srcPkg]:
                self.binPkgMap[pkg] = srcPkg


        # It seems that some packages have versions that don't match up with
        # the source that they were built from. We need to handle that case.
        for binPkgs in self.binNameMap.itervalues():
            for binPkg in binPkgs:
                if binPkg not in self.binPkgMap:
                    pass
                    #log.warn('no source found for %s' % binPkg)
