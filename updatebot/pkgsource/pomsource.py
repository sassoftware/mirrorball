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
Module for interacting with packages defined by pom files
"""

import collections
import logging

from artifactory.pompackage import POM_PARSER
from artifactory.pompackage import STRIP_NAMESPACE_RE
from lxml import etree
import artifactory


log = logging.getLogger('updatebot.pkgsource')


def loaded(func):
    def wrapper(other, *args, **kwargs):
        if other._loaded:
            return
        return func(other, *args, **kwargs)
    return wrapper


class PomSource(object):
    """
    Creates a map of packages from a pom file
    """

    def __init__(self, cfg, ui):
        self._cfg = cfg
        self._ui = ui

        # process excludePackages
        if cfg.packageAll:
            # cfg.package is an additional exclude list
            excludePackages = cfg.excludePackages + cfg.package
            includePackages = []
        else:
            # cfg.package is an explicity include list
            excludePackages = cfg.excludePackages
            includePackages = cfg.package

        self._exclusions = self._buildGAVMap(excludePackages)
        self._inclusions = self._buildGAVMap(includePackages)
        self._pkgMap = {}  # map group, artifact, version to package
        self.pkgQueue = None
        self.chunked = set()
        self._loaded = False

    def _buildGAVMap(self, packages):
        gavMap = {}
        for package in packages:
            gav = package.split(':')
            if len(gav) == 1:
                group = gav
                artifact = '*'
                version = '*'
            elif len(gav) == 2:
                group, artifact = gav
                version = '*'
            elif len(gav) == 3:
                group, artifact, version = gav
            else:
                raise ValueError(
                    'no more than 3 components to package spec: %s' % package)

            gavMap.setdefault(group, {}
                ).setdefault(artifact, set()
                ).add(version)

        return gavMap

    def _includeResult(self, group, artifact, version):
        """Return whether to include result

        A result should be included if the artifact name is not in
        cfg.excludePackages. If the artifact is in cfg.package, then it should
        be included if cfg.packageAll is False, otherwise it should not be
        included.

        @param path: path to filter
        @type path: str
        @return: True if result should be included
        @rtype: bool
        """
        exclusion = self._exclusions.get(group, {})
        exclusion = exclusion.get(artifact) or exclusion.get('*')
        if exclusion and (version in exclusion or '*' in exclusion):
            return False

        if self._cfg.packageAll:
            # cfg.package already mapped into exclusions
            return True
        else:
            # only package what's in _inclusions
            inclusion = self._inclusions.get(group, {})
            inclusion = inclusion.get(artifact) or inclusion.get('*')
            if inclusion and (version in inclusion or '*' in inclusion):
                return True
            return False

    @loaded
    def finalize(self):
        self.pkgQueue = collections.deque(v for v in self._pkgMap.values()
                                          if v is not None)

    @loaded
    def load(self):
        client = artifactory.Client(self._cfg)
        for repo in self._cfg.repositoryPaths:
            log.info('loading repository data %s' % repo)
            archStr = self._cfg.repositoryArch.get(repo, None)
            self.loadFromClient(client, repo, archStr=archStr)

        self.finalize()
        self._loaded = True

    def loadFromClient(self, client, repo, archStr=None):
        for pom in client.quick_search('*.pom', repos=repo):
            if pom.get('mimeType') != 'application/x-maven-pom+xml':
                continue

            # process path into group, artifact, verstion tuple
            path = pom['path'][1:]  # strip the leading /
            # split path and strip file
            group, artifact, version = path.rsplit('/', 3)[:-1]
            group = group.replace('/', '.')  # replace / with . in group
            gav = (group, artifact, version)

            if not self._includeResult(group, artifact, version):
                log.debug('excluding %s from package source', ':'.join(gav))
                continue

            if gav in self._pkgMap:
                # already processed this as a parent or import
                continue

            location = 'repo:%(path)s' % pom
            pomString = client.retrieve_artifact(location)
            pomEtree = etree.fromstring(
                STRIP_NAMESPACE_RE.sub('<project>', pomString, 1),
                parser=POM_PARSER,
                )
            pkg = artifactory.PomPackage(pomEtree, location, client,
                                         self._pkgMap)
            self._pkgMap[gav] = pkg
            pkg.setDependencies(pomEtree, client, self._pkgMap)
