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

import os

import repomd

class PackageChecksumMismatchError(Exception):
    """
    Exception for packages that have checksums that don't match.
    """

    def __init__(self, pkg1, pkg2):
        Exception.__init__(self)
        self.pkg1 = pkg1
        self.pkg2 = pkg2

    def __str___(self):
        return ('The checksums of %s (%s) and %s (%s) do not match.'
                % (self.pkg1, self.pkg1.checksum, self.pkg2,
                   self.pkg2.checksum))


class RpmSource(object):
    """
    Class that builds maps of packages from multiple yum repositories.
    """

    def __init__(self):
        # {srpm: {rpm: path}
        self.rpmMap = dict()

        # {name: srpm}
        self.revMap = dict()

        # {srpm: path}
        self.srcPath = dict()

    def _procSrc(self, basePath, package):
        """
        Process source rpms.
        @param basePath: path to yum repository.
        @type basePath: string
        @param package: package object
        @type package: repomd.packagexml._Package
        """
        shortSrpm = os.path.basename(package.location)
        longLoc = basePath + '/' + package.location
        if shortSrpm in self.srcPath:
            #if package.checksum != self.srcPath[shortSrpm].checksum:
            #    raise PackageChecksumMismatchError(package,
            #                                       self.srcPath[shortSrpm])
            #else:
            #    return
            pass
        else:
            package.location = longLoc
            self.srcPath[shortSrpm] = package

    def _procBin(self, basePath, package):
        """
        Process binary rpms.
        @param basePath: path to yum repository.
        @type basePath: string
        @param package: package object
        @type package: repomd.packagexml._Package
        """
        srpm = package.sourcerpm
        longLoc = basePath + '/' + package.location
        package.location = longLoc
        if self.rpmMap.has_key(srpm):
            shortLoc = os.path.basename(package.location)
            # remove duplicates of this binary RPM - last one wins
            existing = [ x for x in self.rpmMap[srpm].iterkeys()
                         if os.path.basename(x) == shortLoc ]
            for key in existing:
                del self.rpmMap[srpm][key]
            self.rpmMap[srpm][longLoc] = package
        else:
            self.rpmMap[srpm] = {longLoc: package}
        self.revMap[package.name] = srpm

    def load(self, url, basePath=''):
        """
        Walk the yum repository rooted at url/basePath and collect information
        about rpms found.
        @param url: url to common directory on host where all repositories resides.
        @type url: string
        @param basePath: directory where repository resides.
        @type basePath: string
        """

        client = repomd.Client(url + '/' + basePath)
        self.loadFromClient(client)

    def loadFromClient(self, client, basePath=''):
        '''
        Walk the yum repository rooted at url/basePath and collect information
        about rpms found.
        @param client: client object for extracting data from the repo metadata
        @type client: repomd.Client
        @param basePath: path to prefix location metadata with
        @type basePath: string
        '''

        for pkg in client.getPackageDetail():
            # ignore the 32-bit compatibility libs - we will
            # simply use the 32-bit components from the repository
            if '32bit' in pkg.name:
                continue

            if pkg.sourcerpm == '':
                self._procSrc(basePath, pkg)
            else:
                self._procBin(basePath, pkg)

    def getNames(self, src):
        """
        @return list that goes into the rpms line in the recipe.
        """

        names = set([ x.name for x in self.rpmMap[src].itervalues() ])
        return names

    def getRPMS(self, src):
        """
        @return list of binary RPMS built from this source.
        """
        return [ x for x in self.rpmMap[src].itervalues() ]

    def getSrpms(self, pkglist):
        """
        Get source RPMS for a given list of binary RPM package names
        """
        srpms = list()
        for p in pkglist:
            srpms.append(self.revMap[p])
        return srpms

    def getArchs(self, src):
        """
        @return list that goes into the archs line in the recipe.
        """

        archs = set([ x.arch for x in self.rpmMap[src].itervalues() ])
        if 'i586' in archs and 'i686' in archs:
            # remove the base arch if we have an extra arch
            arch = self.getExtraArchs(src)[0]
            if arch == 'i686':
                archs.remove('i586')
        return archs

    def getExtraArchs(self, src):
        """
        For the special case of RPMs that have components optimized for the
        i686 architecture while other components are at i586, then return
        ('i686', set(rpms that are i686 only)), otherwise return (None, None).
        """

        hdrs = [ (x.arch, x.name) for x in self.rpmMap[src].itervalues() ]
        archMap = {}
        for arch, name in hdrs:
            if arch in archMap:
                archMap[arch].add(name)
            else:
                archMap[arch] = set((name,))
        if 'i586' in archMap and 'i686' in archMap:
            if archMap['i586'] != archMap['i686']:
                return 'i686', archMap['i686']
        return None, None

    def createManifest(self, srpm):
        """
        @return the text for the manifest file.
        """
        l = []
        l.append(self.srcPath[srpm].location)
        l.extend([x.location for x in self.getRPMS(srpm)])
        # add a trailing newline
        return '\n'.join(sorted(l) + [''])
