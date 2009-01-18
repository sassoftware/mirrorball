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
Advisory module for Ubuntu.
"""

import pmap
import logging

from updatebot.errors import AdvisoryError
from updatebot.advisories.common import BaseAdvisor

log = logging.getLogger('updatebot.advisories')

class Advisor(BaseAdvisor):
    """
    Class for processing Ubuntu advisory information.
    """

    def load(self):
        """
        Parse the required data to generate a mapping of binary package
        object to patch object for a given platform into self._pkgMap.
        """

        # Build data structure for looking up srcPkgs based on file path in
        # the advisory.
        pkgCache = {}
        for pkg in self._pkgSource.binPkgMap:
            # is a source package
            if hasattr(pkg, 'files'):
                files = pkg.files
            elif hasattr(pkg, 'location'):
                files = [pkg.location, ]

            for path in set(files):
                if path not in pkgCache:
                    pkgCache[path] = set()
                pkgCache[path].add(pkg)

        # Fetch all of the archives and process them.
        for url in self._getArchiveUrls():
            log.info('parsing mail archive: %s' % url)
            for msg in pmap.parse(url, backend=self._cfg.platformName):
                self._loadOne(msg, pkgCache)

    def _loadOne(self, msg, pkgCache):
        """
        Handles matching one message to any mentioned packages.
        """

        if self._filterPatch(msg):
            return

        if self._cfg.upstreamProductVersion not in msg.pkgNameVersion:
            return

        for path in msg.pkgs:
            if path not in pkgCache:
                #log.warn('found path (%s) not in cache' % path)
                continue

            #import epdb; epdb.st()
            log.info('found path (%s) in cache' % path)
            nvMap = msg.pkgNameVersion[self._cfg.upstreamProductVersion]
            for pkg in pkgCache[path]:
                nv = (pkg.name, '-'.join([pkg.version, pkg.release]))
                if nv[1].startswith('-') or nv[1].endswith('-'):
                    raise AdvisoryError
                if nv in nvMap:
                    if pkg not in self._pkgMap:
                        self._pkgMap[pkg] = set()
                    self._pkgMap[pkg].add(msg)

                    if msg.packages is None:
                        msg.packages = set()
                    msg.packages.add(pkg)


    def _hasException(self, binPkg):
        """
        Check the config for repositories with exceptions for sending
        advisories. (io. repositories that we generated metadata for.)
        @param binPkg: binary package object
        @type binPkg: repomd.packagexml._Package
        """

        # W0613 - Unused argument
        # pylint: disable-msg=W0613

        return False

    def _isUpdatesRepo(self, binPkg):
        """
        Check the repository name. If this package didn't come from a updates
        repository it is probably not security related.
        @param binPkg: binary package object
        @type binPkg: repomd.packagexml._Package
        """

        # W0613 - Unused argument
        # pylint: disable-msg=W0613

        return True

    def _checkForDuplicates(self, patchSet):
        """
        Check a set of "patch" objects for duplicates. If there are duplicates
        combine any required information into the first object in the set and
        return True, otherwise return False.
        """

        # W0613 - Unused argument
        # pylint: disable-msg=W0613

        return False
