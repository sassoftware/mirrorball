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
