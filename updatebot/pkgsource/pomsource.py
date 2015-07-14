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

from artifactory.errors import MissingProjectError
from artifactory.pompackage import PomPackage
from conary.lib import graph
import artifactory

from ..config import MavenCoordinateGlobList
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

        self._exclusions = cfg.excludePoms.copy()
        self._inclusions = None

        # process excludePackages
        if cfg.packageAll:
            # cfg.package is an additional exclude list
            self._exclusions.extend(cfg.package)
        else:
            # cfg.package is an explicity include list
            self._inclusions = MavenCoordinateGlobList()
            self._inclusions.extend(cfg.package)

        self._pkgMap = {}  # map group, artifact, version to package
        self.pkgQueue = graph.DirectedGraph()
        self._loaded = False

    def _iterPackages(self, client, repo=None):
        searchKwargs = {}
        if repo:
            searchKwargs = {'repos': repo}
        if self._inclusions is not None:
            searchFunc = client.gavc_search
            searchArgs = [package.split(':') for package in self._cfg.package]
        else:
            searchFunc = client.quick_search
            searchArgs = (["*.pom"],)

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

        :param path: path to filter
        :type path: str
        :return: True if result should be included
        :rtype: bool
        """
        coordinate = ':'.join((group, artifact, version))
        if coordinate in self._exclusions:
            return False

        if self._cfg.packageAll:
            # cfg.package already mapped into exclusions
            return True
        else:
            return coordinate in self._inclusions

    @loaded
    def finalize(self):
        for node in self.pkgQueue.iterNodes():
            self.pkgQueue.addEdges((node, dep, 1) for dep in node.dependencies)

    @loaded
    def load(self):
        client = artifactory.Client(self._cfg)
        log.info('loading repository data')
        self.loadFromClient(client)
        self.finalize()
        self._loaded = True

    def loadFromClient(self, client):
        for result in self._iterPackages(client):
            log.debug("loading %s", result["path"])
            # process path into group, artifact, verstion tuple
            path = result['path'][1:]  # strip the leading /
            # split path and strip file
            segments = path.rsplit('/', 3)
            if len(segments) == 4:
                group, artifact, version, _ = segments
            else:
                group, artifact, _ = segments
                version = ''
            group = group.replace('/', '.')  # replace / with . in group
            gav = (group, artifact, version)

            if not self._includeResult(*gav):
                log.info('excluding %s from package source', ':'.join(gav))
                continue

            if gav not in self._pkgMap:
                # this is a new package
                try:
                    location = client.constructPath(*gav)
                    pkg = PomPackage("%s:%s:pom:%s" % gav, location, client,
                                     self._pkgMap)
                except MissingProjectError:
                    log.error("Could not load %s:%s:%s", *gav)
                    continue
            else:
                log.debug("already processed %s", ':'.join(gav))
                pkg = self._pkgMap[gav]

            if not pkg:
                continue

            self.pkgQueue.addNode(pkg)
            for dep in util.recurseDeps(pkg):
                self.pkgQueue.addNode(dep)
