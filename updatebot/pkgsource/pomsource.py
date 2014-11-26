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

from lxml import etree
import artifactory
import prism_rest_client

from .pkgcache import PkgCache


log = logging.getLogger('updatebot.pkgsource')

xmlParser = etree.XMLParser(recover=True, remove_comments=True, remove_pis=True)


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

    def _packageFactory(self, pomResource, xmlString, client, repo, archStr):
        """Create a `artifactory.Package` from xmlString
        """
        # process path into group, artifact, verstion tuple
        path = pomResource['path'][1:]  # strip the leading /
        gav = path.rsplit('/', 3)[:-1]  # split portions of path and strip file
        gav[0] = gav[0].replace('/', '.')  # replace / with . in group
        gav = tuple(gav)  # convert to tuple

        if gav in self.pkgMap:
            return self.pkgMap[gav]

        xml = etree.fromstring(xmlString, parser=xmlParser)
        ns = ('{%s}' % xml.nsmap[None]) if None in xml.nsmap else ''

        parent = xml.find("%sparent" % ns)
        if parent is not None:
            parentGAV = (parent.find('%sgroupId' % ns).text.strip(),
                         parent.find('%sartifactId' % ns).text.strip(),
                         parent.find('%sversion' % ns).text.strip(),
                         )
            if parentGAV in self.pkgMap:
                parent = self.pkgMap[parentGAV]
            else:
                results = [r for r in client.gavc_search(*parentGAV)
                           if r['mimeType'] == 'application/x-maven-pom+xml']

                if not results:
                    log.warning('Parent pom of %s is not cached: %s',
                                '/'.join(gav), '/'.join(parentGAV))
                    parent = None
                else:
                    if len(results) > 1:
                        log.warning("Multiple parent pom files found for %s",
                                    '/'.join(gav))
                    parentResource = results[0]
                    parentXml = client.retrieve_artifact('%(repo)s:%(path)s' %
                                                         parentResource)
                    parent = self._packageFactory(
                        parentResource,
                        parentXml.text.encode('utf8'),
                        client,
                        repo,
                        archStr,
                        )
                # add the parent to the map
                self.pkgMap[parentGAV] = parent

        artifacts = list(client.gavc_search(*gav, repos=repo))
        if not artifacts:
            raise Exception('No artifacts associated with %s', '/'.join(gav))

        package = artifactory.PomPackage(gav, pomResource, xml, parent,
                                         artifacts, archStr)

        # add the package to the pkgMap
        self.pkgMap[gav] = package

        return package

    @loaded
    def finalize(self):
        self.pkgQueue = collections.deque(v for v in self.pkgMap.values()
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
        for pom in client.quick_search('pom', repos=repo):
            if pom.get('mimeType') != 'application/x-maven-pom+xml':
                continue

            if not self._includeResult(pom['path']):
                continue

            location = '%(repo)s:%(path)s' % pom
            xmlString = client.retrieve_artifact(location).text.encode('utf8')
            self._packageFactory(pom, xmlString, client, repo, archStr)


class PomSourceCache(PomSource, PkgCache):

    def __init__(self, cfg, ui):
        PkgCache.__init__(self, cfg, ui)
        PomSource.__init__(self, cfg, ui)

        self._api = prism_rest_client.open(self._cfg.pkgcacheUri)

        self._loaded = False
        self._cfg.synthesizeSources = False
