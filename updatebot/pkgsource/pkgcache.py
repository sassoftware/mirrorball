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
Module for interacting with a pkgcache service.
"""

import os
import logging

log = logging.getLogger('updatebot.pkgsource')

import prism_rest_client

from rpmutils import NEVRA
from updatebot.pkgsource.yumsource import loaded
from updatebot.pkgsource.yumsource import YumSource as PackageSource

class Package(object):
    __slots__ = ('_pkg', )

    def __init__(self, pkg):
        self._pkg = pkg

    @property
    def name(self):
        return self._pkg.nevra.name

    @property
    def epoch(self):
        return self._pkg.nevra.epoch

    @property
    def version(self):
        return self._pkg.nevra.version

    @property
    def release(self):
        return self._pkg.nevra.release

    @property
    def arch(self):
        return self._pkg.nevra.arch

    @property
    def location(self):
        return self._pkg.location

    @property
    def sourcerpm(self):
        return os.path.basename(self._pkg.sourcepkg.location)

    @property
    def buildTimestamp(self):
        return 1

    def getConaryVersion(self):
        assert self.arch == 'src'
        filename = os.path.basename(self.location)
        nvr = '.'.join(filename.split('.')[:-2])
        v = '_'.join(nvr.split('-')[-2:])
        return v

    def getNevra(self):
        return NEVRA(self.name, str(self.epoch), self.version, self.release, self.arch)

    def getFileName(self):
        return '%s-%s-%s.%s.rpm' % (self.name, self.version, self.release, self.arch)

    def __hash__(self):
        return hash((self.getNevra(), os.path.basename(self.location)))

    def __cmp__(self, other):
        assert isinstance(other, self.__class__)
        c = cmp(self.getNevra(), other.getNevra())
        if c != 0: return c
        # If the filename matches, assume that the files are identical, even if
        # they are in different paths in the mirror.
        return cmp(os.path.basename(self.location),
                   os.path.basename(other.location))

    def __str__(self):
        return self.getFileName()

    __repr__ = __str__


class PkgCache(PackageSource):
    """
    pkgSource for interacting with a pkgcache server.
    """

    def __init__(self, cfg, ui):
        PackageSource.__init__(self, cfg, ui)

        self._api = prism_rest_client.open(self._cfg.pkgcacheUri, verify=False)

        self._loaded = False
        self._cfg.synthesizeSources = False

    @loaded
    def load(self):
        """
        Method to parse all package data into data structures listed above.
        NOTE: This method should be implmented by all backends.
        """

        log.info('loading package source from cache')
        distros = dict(((x.name, x.version), x) for x in self._api.distros)
        distro = distros.get((self._cfg.platformName,
            self._cfg.upstreamProductVersion))

        self._distro = distro

        log.info('fetching packages for %s', self._distro.name)
        pkgs = self._distro.packages
        for pkg in pkgs:
            self._distro._cache[pkg._data.id] = pkg
        log.info('finished fetching packages')

        for pkg in self._distro.packages:
            if pkg.nevra.arch in self._excludeArch:
                continue

            assert '-' not in pkg.nevra.version
            assert '-' not in pkg.nevra.release

            if self._excludeLocation(pkg.location):
                continue

            if pkg.nevra.arch == 'src':
                self._procSrc(Package(pkg))
            else:
                self._procBin(Package(pkg), archStr=pkg.repo.arch)

        self.finalize()
        self._loaded = True
