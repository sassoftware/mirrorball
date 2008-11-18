#
# Copyright (c) 2006,2008 rPath, Inc.
#
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
Module for interacting with packages in multiple yum repositories.
"""

import logging

import repomd
from updatebot import util

log = logging.getLogger('updatebot.pkgsource')

class RpmSource(object):
    """
    Class that builds maps of packages from multiple yum repositories.
    """

    def __init__(self, cfg):
        self._cfg = cfg
        self._excludeArch = self._cfg.excludeArch

        # {srcTup: srpm}
        self._srcMap = dict()

        # {srcTup: {rpm: path}
        self._rpmMap = dict()

        # set of all src pkg objects
        self._srcPkgs = set()

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

    def getClients(self):
        """
        Get instances of repository clients.
        """

        if not self._clients:
            self.load()

        return self._clients

    def load(self):
        """
        Load package source based on config data.
        """

        for repo in self._cfg.repositoryPaths:
            log.info('loading repository data %s' % repo)
            client = repomd.Client(self._cfg.repositoryUrl + '/' + repo)
            self.loadFromClient(client, repo)
            self._clients[repo] = client

        self.finalize()

    def loadFromUrl(self, url, basePath=''):
        """
        Walk the yum repository rooted at url/basePath and collect information
        about rpms found.
        @param url: url to common directory on host where all repositories resides.
        @type url: string
        @param basePath: directory where repository resides.
        @type basePath: string
        """

        client = repomd.Client(url + '/' + basePath)
        self.loadFromClient(client, basePath=basePath)

    def loadFromClient(self, client, basePath=''):
        """
        Walk the yum repository rooted at url/basePath and collect information
        about rpms found.
        @param client: client object for extracting data from the repo metadata
        @type client: repomd.Client
        @param basePath: path to prefix location metadata with
        @type basePath: string
        """

        for pkg in client.getPackageDetail():
            # ignore the 32-bit compatibility libs - we will
            # simply use the 32-bit components from the repository
            if '32bit' in pkg.name:
                continue

            # Don't use all arches.
            if pkg.arch in self._excludeArch:
                continue

            assert '-' not in pkg.version
            assert '-' not in pkg.release

            pkg.location = basePath + '/' + pkg.location

            # ignore 32bit rpms in a 64bit repo.
            if pkg.arch in ('i386', 'i586', 'i686') and 'x86_64' in pkg.location:
                continue

            if pkg.sourcerpm == '':
                self._procSrc(pkg)
            else:
                self._procBin(pkg)

    def _procSrc(self, package):
        """
        Process source rpms.
        @param package: package object
        @type package: repomd.packagexml._Package
        """

        if package.name not in self.srcNameMap:
            self.srcNameMap[package.name] = set()
        self.srcNameMap[package.name].add(package)

        self.locationMap[package.location] = package

        self._srcPkgs.add(package)
        self._srcMap[(package.name, package.epoch, package.version, package.release, package.arch)] = package

    def _procBin(self, package):
        """
        Process binary rpms.
        @param package: package object
        @type package: repomd.packagexml._Package
        """

        # FIXME: There should be a better way to figure out the tuple that
        #        represents the hash of the srcPkg.
        srcParts = package.sourcerpm.split('-')
        srcName = '-'.join(srcParts[:-2])
        srcVersion = srcParts[-2]
        if srcParts[-1].endswith('.src.rpm'):
            srcRelease = srcParts[-1][:-8] # remove '.src.rpm'
        elif srcParts[-1].endswith('.nosrc.rpm'):
            srcRelease = srcParts[-1][:-10]
        rpmMapKey = (srcName, package.epoch, srcVersion, srcRelease, 'src')
        if rpmMapKey not in self._rpmMap:
            self._rpmMap[rpmMapKey] = set()
        self._rpmMap[rpmMapKey].add(package)

        if package.name not in self.binNameMap:
            self.binNameMap[package.name] = set()
        self.binNameMap[package.name].add(package)

        self.locationMap[package.location] = package

    def finalize(self):
        """
        Make some final datastructures now that we are done populating object.
        """

        # Now that we have processed all of the rpms, build some more data
        # structures.
        count = 0
        for pkg in self._srcPkgs:
            key = (pkg.name, pkg.epoch, pkg.version, pkg.release, pkg.arch)
            if pkg in self.srcPkgMap:
                continue

            if key not in self._rpmMap:
                #log.warn('found source without binary rpms: %s' % pkg)
                #log.debug(key)
                #log.debug([ x for x in self._rpmMap if x[0] == key[0] ])

                count += 1
                if pkg in self.srcNameMap[pkg.name]:
                    self.srcNameMap[pkg.name].remove(pkg)
                continue

            self.srcPkgMap[pkg] = self._rpmMap[key]
            self.srcPkgMap[pkg].add(pkg)
            del self._rpmMap[key]

            for binPkg in self.srcPkgMap[pkg]:
                self.binPkgMap[binPkg] = pkg

        if count > 0:
            log.warn('found %s source rpms without matching binary rpms' % count)

        # Attempt to match up remaining binaries with srpms.
        for srcTup in self._rpmMap.keys():
            srcKey = list(srcTup)
            epoch = int(srcKey[1])
            while epoch >= 0:
                srcKey[1] = str(epoch)
                key = tuple(srcKey)
                if key in self._srcMap:
                    srcPkg = self._srcMap[key]
                    for binPkg in self._rpmMap[srcTup]:
                        self.srcPkgMap[srcPkg].add(binPkg)
                        self.binPkgMap[binPkg] = srcPkg
                    del self._rpmMap[srcTup]
                    break
                epoch -= 1

        if self._rpmMap:
            count = sum([ len(x) for x in self._rpmMap.itervalues() ])
            log.warn('found %s binary rpms without matching srpms' % count)

    def loadFileLists(self, client, basePath):
        for pkg in client.getFileLists():
            for binPkg in self.binPkgMap.iterkeys():
                if util.packageCompare(pkg, binPkg) == 0:
                    binPkg.files = pkg.files
                    break
