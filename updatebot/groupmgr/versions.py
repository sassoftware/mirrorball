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
