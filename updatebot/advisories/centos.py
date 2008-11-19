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

import os
import time
import pmap
import logging

from updatebot.update import Updater
from updatebot.advisories.common import BaseAdvisor

log = logging.getLogger('updatebot.advisories')

class Advisor(BaseAdvisor):
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
            for msg in pmap.parse(url, backend=self._cfg.platformName):
                self._loadOne(msg, pkgCache)

    def _getArchiveUrls(self):
        """
        Compute archive urls to load.
        """

        base = self._cfg.listArchiveBaseUrl
        startDate = self._cfg.listArchiveStartDate
        timeTup = list(time.strptime(startDate, '%Y%m'))

        startYear = timeTup[0]
        startMonth = timeTup[1]

        endYear = time.localtime()[0]
        endMonth = time.localtime()[1]

        while timeTup[0] <= endYear:
            if timeTup[0] != startYear:
                timeTup[1] = 1

            if timeTup[0] == endYear:
                end = endMonth
            else:
                end = 12

            while timeTup[1] <= end:
                fname = time.strftime('%Y-%B.txt.gz', timeTup)
                yield '/'.join([base, fname])

                timeTup[1] += 1

            timeTup[0] += 1

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
            if arch in msg.subject:
                msg.subject = msg.subject.replace('%s ' % arch, '')

        # Strip subject.
        msg.subject = msg.subject.replace('[CentOS-announce]', '')
        msg.subject = msg.subject.strip()

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
        advisories. (io. repositories that we generated metadata for.)
        @param binPkg: binary package object
        @type binPkg: repomd.packagexml._Package
        """

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
