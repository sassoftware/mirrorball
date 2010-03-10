#
# Copyright (c) 2009-2010 rPath, Inc.
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
Module for generating platform versions from some upstream source.
"""

import copy

from updatebot.pkgsource import RpmSource

class URLVersionSource(object):
    """
    Class for handling the indexing and comparison of ISO contents.
    """

    def __init__(self, cfg, version, url):
        self._cfg = cfg
        self._version = version
        self._url = url

        pkgSource = RpmSource(cfg, )
        pkgSource.loadFromUrl(url)
        pkgSource.finalize()
        pkgSource.setLoaded()

        self._sourceSet = set([ x for x in pkgSource.iterPackageSet() ])

    def areWeHereYet(self, pkgSet):
        """
        Figure out if the given package set is this version.
        @param pkgSet: set of source names and source versions
        @type pkgSet: set([(conarySourceName, conarySourceVersion)])
        @return boolean
        """

        # Make sure that all versions that are on the ISO are in the conary
        # repository. It appears to be a common case that the ISO is missing
        # content from RHN.
        return not self._sourceSet.difference(pkgSet)


class VersionFactory(object):
    """
    Class for generating group verisons from a variety of sources.
    """

    def __init__(self, cfg):
        self._cfg = copy.deepcopy(cfg)
        self._cfg.synthesizeSources = True
        self._sources = {}

        for version, url in sorted(cfg.versionSources.iteritems()):
            self._sources[version] = URLVersionSource(self._cfg, version, url)

    def getVersions(self, pkgSet):
        """
        Given the available package sources find the current versions.
        """

        versions = []
        for version, source in sorted(self._sources.iteritems()):
            if source.areWeHereYet(pkgSet):
                versions.append(version)
        return set(versions)
