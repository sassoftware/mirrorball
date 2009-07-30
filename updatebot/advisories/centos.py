#
# Copyright (c) 2008-2009 rPath, Inc.
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
Advisory module for CentOS.
"""

import re
import os
import pmap
import logging

from updatebot.advisories.common import BaseAdvisor

log = logging.getLogger('updatebot.advisories')

class Advisor(BaseAdvisor):
    """
    Class for processing CentOS advisory information.
    """

    supportedArches = ('i386', 'i586', 'i686', 'x86_64', 'noarch', 'src')

    def load(self):
        """
        Parse the required data to generate a mapping of binary package
        object to patch object for a given platform into self._pkgMap.
        """

        # Build data structure for looking up packages based on basename.
        pkgCache = {}
        for binPkg in self._pkgSource.binPkgMap:
            baseName = os.path.basename(binPkg.location)
            if baseName not in pkgCache:
                pkgCache[baseName] = set()
            pkgCache[baseName].add(binPkg)

        # Fetch all of the archives and process them.
        for url in self._getArchiveUrls():
            log.info('parsing mail archive: %s' % url)
            try:
                for msg in pmap.parse(url, backend=self._cfg.platformName,
                    productVersion=self._cfg.upstreamProductVersion):
                    self._loadOne(msg, pkgCache)
            except pmap.ArchiveNotFoundError, e:
                log.warn('unable to retrieve archive for %s' % url)

    def _loadOne(self, msg, pkgCache):
        """
        Handles matching one message to any mentioned packages.
        """

        if self._filterPatch(msg):
            return

        # Toss any messages that do not have packages associated with them.
        if msg.pkgs is None:
            return

        # Strip arch out of the subject
        for arch in self.supportedArches:
            if arch in msg.summary:
                msg.summary = msg.summary.replace('%s ' % arch, '')

        # Strip subject.
        msg.summary = msg.summary.replace('[CentOS-announce]', '')
        msg.summary = msg.summary.strip()

        for pkgName in msg.pkgs:
            # Toss out any arches that we don't know how to handle.
            if not self._supportedArch(pkgName):
                continue

            if pkgName not in pkgCache:
                #log.warn('found %s in msg, but not in pkgCache' % pkgName)
                continue

            for binPkg in pkgCache[pkgName]:
                if binPkg not in self._pkgMap:
                    self._pkgMap[binPkg] = set()
                self._pkgMap[binPkg].add(msg)

                if msg.packages is None:
                    msg.packages = set()
                msg.packages.add(binPkg)

    def _supportedArch(self, pkgfn):
        """
        Filter out unsupported arches based on rpm filename.
        """

        dotPos = pkgfn[:-4].rindex('.')
        arch = pkgfn[dotPos + 1:-4]
        if arch in self.supportedArches:
            return True
        return False

    def _hasException(self, binPkg):
        """
        Check the config for repositories with exceptions for sending
        advisories. (ie. repositories that we generated metadata for.)
        @param binPkg: binary package object
        @type binPkg: repomd.packagexml._Package
        """

        # W0613 - Unused argument binPkg
        # pylint: disable-msg=W0613

        for fltr in self._cfg.advisoryException:
            path, exp = fltr[0].split()
            if path in binPkg.location and re.match(exp, binPkg.name):
                return True

        return False

    def _isUpdatesRepo(self, binPkg):
        """
        Check the repository name. If this package didn't come from a updates
        repository it is probably not security related.
        @param binPkg: binary package object
        @type binPkg: repomd.packagexml._Package
        """

        parts = binPkg.location.split('/')
        if parts[1] == 'updates':
            return True
        return False

    def _checkForDuplicates(self, patchSet):
        """
        Check a set of "patch" objects for duplicates. If there are duplicates
        combine any required information into the first object in the set and
        return True, otherwise return False.
        """

        if not len(patchSet):
            return False

        primary = list(patchSet)[0]
        for patch in patchSet:
            if patch is primary:
                continue

            # Thse are the same if they use the same advisory.
            if primary.upstreamAdvisoryUrl != patch.upstreamAdvisoryUrl:
                return False

            # Copy pkg data into the primary
            primary.pkgs.update(patch.pkgs)
            primary.packages.update(patch.packages)
        return True
