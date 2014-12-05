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
import prism_rest_client

from .pkgcache import PkgCache


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

        self.pkgMap = {}  # map group, artifact, version to package
        self._pkgQueue = collections.deque([])

        self._loaded = False

    def _includeResult(self, path):
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
        artifact = path.split('/')[-3]

        if artifact in self._cfg.excludePackages:
            return False

        if artifact in self._cfg.package:
            return not self._cfg.packageAll

        return self._cfg.packageAll

    @loaded
    def finalize(self):
        self.pkgQueue = collections.deque(v for v in self.pkgMap.values()
                                          if v is not None)

    @loaded
    def load(self):
        client = artifactory.Client(self._cfg)
        for repo in self._cfg.repositoryPaths:
            # FIXME: need a better way to handle this.
            if repo != 'repo1-cache':
                # i only want to resolve other repos if a package resolves its
                # deps or parents there, otherwise ignore it
                continue
            log.info('loading repository data %s' % repo)
            archStr = self._cfg.repositoryArch.get(repo, None)
            self.loadFromClient(client, repo, archStr=archStr)

        self.finalize()
        self._loaded = True

    def loadFromClient(self, client, repo, archStr=None):
        for pom in client.quick_search('pom', repos=repo):
            if pom.get('mimeType') != 'application/x-maven-pom+xml':
                continue

            if not self._includeResult(pom['path']):
                continue

            # process path into group, artifact, verstion tuple
            path = pom['path'][1:]  # strip the leading /
            gav = path.rsplit('/', 3)[:-1]  # split path and strip file
            gav[0] = gav[0].replace('/', '.')  # replace / with . in group
            gav = tuple(gav)  # convert to tuple

            if gav in self.pkgMap:
                # already processed this as a parent or import
                continue

            location = '%(repo)s:%(path)s' % pom
            pomString = client.retrieve_artifact(location)
            pomEtree = etree.fromstring(
                STRIP_NAMESPACE_RE.sub('<project>', pomString, 1),
                parser=POM_PARSER,
                )
            pkg = artifactory.PomPackage(pomEtree, location, client,
                                         self.pkgMap)
            self.pkgMap[gav] = pkg
            pkg.setDependencies(pomEtree, client, self.pkgMap)


class PomSourceCache(PomSource, PkgCache):

    def __init__(self, cfg, ui):
        PkgCache.__init__(self, cfg, ui)
        PomSource.__init__(self, cfg, ui)

        self._api = prism_rest_client.open(self._cfg.pkgcacheUri)

        self._loaded = False
        self._cfg.synthesizeSources = False
