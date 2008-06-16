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

"""
Module for managing/manipulating advisories.
"""

import logging

from updatebot.errors import NoAdvisoryFoundError

log = logging.getLogger('updatebot.advisor')

class Advisor(object):
    """
    Class for managing, manipulating, and distributing advisories.
    """

    def __init__(self, cfg, rpmSource, patchSource):
        self._cfg = cfg
        self._rpmSource = rpmSource
        self._patchSource = patchSource

        # { ((name, version, flavor), srcPkg): [ patchObj, ... ]
        self._cache = dict()

    def check(self, trvLst):
        """
        Check to see if there are advisories for troves in trvLst.
        @param trvLst: list of troves and srpms.
        @type trvLst: [((name, version, flavor), srcPkg), ... ]
        """

        for nvf, srcPkg in trvLst:
            patches = set()
            for binPkg in self._rpmSource.srcPkgMap[srcPkg]:
                # Don't check srpms.
                if binPkg is srcPkg:
                    continue

                if binPkg in self._patchSource.pkgMap:
                    patches.update(self._patchSource.pkgMap[binPkg])
                elif self._hasException(binPkg):
                    log.info('found advisory exception for %s' % binPkg)
                    log.debug(binPkg.location)
                elif not self._isSecurity(binPkg):
                    log.info('package not in updates repository %s' % binPkg)
                    log.debug(binPkg.location)
                else:
                    log.error('could not find patch for %s' % binPkg)
                    raise NoAdvisoryFoundError(why=binPkg)

            if (nvf, srcPkg) not in self._cache:
                self._cache[(nvf, srcPkg)] = patches


    def _hasException(self, binPkg):
        """
        Check the config for repositories with exceptions for sending
        advisories. (io. repositories that we generated metadata for.)
        @param binPkg: binary package object
        @type binPkg: repomd.packagexml._Package
        """

        shortPath = binPkg.location.split('/')[0]

        for advisoryException in self._cfg.advisoryException:
            path = advisoryException[0].split('/')[0]
            if path == shortPath:
                return True
        return False

    @classmethod
    def _isSecurity(self, binPkg):
        """
        Check the repository name. If this package didn't come from a updates
        repository it is probably not security related.
        @param binPkg: binary package object
        @type binPkg: repomd.packagexml._Package
        """

        # FIXME: Make sure this is a sane check.

        shortPath = binPkg.location.split('/')[0]

        if shortPath.endswith('Updates'):
            return True
        else:
            return False
