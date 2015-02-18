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

import logging

from artifactory.pompackage import POM_PARSER
from artifactory.pompackage import STRIP_NAMESPACE_RE
from artifactory.pompackage import createPomPackage
from conary.lib import graph
from lxml import etree
import artifactory

from ..lib import util


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
        self.pkgQueue = graph.DirectedGraph()
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

    def _iterPackages(self, client, repo=None):
        searchKwargs = {}
        if repo:
            searchKwargs = {'repos': repo}
        if self._inclusions:
            searchFunc = client.gavc_search
            searchArgs = [package.split(':') for package in self._cfg.package]
        else:
            searchFunc = client.quick_search
            searchArgs = [ ["*.pom"], ]

        for args in searchArgs:
            for result in searchFunc(*args, **searchKwargs):
                if result["mimeType"] == "application/x-maven-pom+xml":
                    yield result

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
        for node in self.pkgQueue.iterNodes():
            self.pkgQueue.addEdges((node, dep, 1) for dep in node.dependencies)

    @loaded
    def load(self):
        client = artifactory.Client(self._cfg)
        for path in self._cfg.repositoryPaths:
            log.info('loading repository data %s', path)
            archStr = self._cfg.repositoryArch.get(path, None)
            self.loadFromClient(client, archStr=archStr)
        self.finalize()
        self._loaded = True

    def loadFromClient(self, client, repo=None, archStr=None):
        for result in self._iterPackages(client):
            log.debug('loading %s', result['path'])
            # process path into group, artifact, verstion tuple
            path = result['path'][1:]  # strip the leading /
            # split path and strip file
            group, artifact, version = path.rsplit('/', 3)[:-1]
            group = group.replace('/', '.')  # replace / with . in group
            gav = (group, artifact, version)

            if self._inclusions and not \
                    self._includeResult(group, artifact, version):
                log.debug('excluding %s from package source', ':'.join(gav))
                continue

            if gav not in self._pkgMap:
                # this is a new package
                pkg = createPomPackage(*gav, client=client, cache=self._pkgMap)
            else:
                pkg = self._pkgMap[gav]

            self.pkgQueue.addNode(pkg)
            for dep in util.recurseDeps(pkg):
                self.pkgQueue.addNode(dep)
