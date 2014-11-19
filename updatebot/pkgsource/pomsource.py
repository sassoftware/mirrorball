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
Module for interacting with packages defined by pom files
"""

import logging

import artifactory
import prism_rest_client

from updatebot.pkgsource.common import BasePackageSource
from updatebot.pkgsource.pkgcache import PkgCache


log = logging.getLogger('updatebot.pkgsource')


def loaded(func):
    def wrapper(other, *args, **kwargs):
        if other._loaded:
            return
        return func(other, *args, **kwargs)
    return wrapper


class PomSource(BasePackageSource):
    """
    Creates a map of packages from a pom file
    """

    def __init__(self, cfg, ui):
        BasePackageSource.__init__(self, cfg, ui)
        self._srcPkgs = set()
        self._binMap = {}

    def _procSrc(self, package):
        self.srcNameMap.setdefault(package.name, set()).add(package)
        self.locationMap[package.location] = package
        self._srcPkgs.add(package)

    def _procBin(self, package, archStr=None):
        key = package.getNevra()[:-1] + ('src',)
        self._binMap.setdefault(key, set()).add(package)
        self.binNameMap.setdefault(package.name, set()).add(package)
        self.locationMap[package.location] = package

    @loaded
    def finalize(self):
        for pkg in self._srcPkgs:
            if pkg in self.srcPkgMap:
                continue

            self.srcPkgMap[pkg] = list(self._binMap[pkg.getNevra()])
            for binPkg in self.srcPkgMap[pkg]:
                self.binPkgMap[binPkg] = pkg

    @loaded
    def load(self):
        client = artifactory.Client(self._cfg)
        for repo in self._cfg.repositoryPaths:
            log.info('loading repository data %s' % repo)
            archStr = self._cfg.repositoryArch.get(repo, None)
            self.loadFromClient(client, repo, archStr=archStr)

        self.finalize()
        self._loaded = True

    def loadFromClient(self, client, repo, archStr=None):
        for pkg in client.getPackageDetails(repo, archStr):
            if pkg.arch == 'src':
                self._procSrc(pkg)
            else:
                self._procBin(pkg, archStr)


class PomSourceCache(PomSource, PkgCache):

    def __init__(self, cfg, ui):
        PkgCache.__init__(self, cfg, ui)
        PomSource.__init__(self, cfg, ui)

        self._api = prism_rest_client.open(self._cfg.pkgcacheUri)

        self._loaded = False
        self._cfg.synthesizeSources = False
