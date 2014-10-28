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

from functools import wraps
import logging

from lxml import objectify
import artifactory

from updatebot.pkgsource.common import BasePackageSource


XMLParser = objectify.makeparser(recover=True, remove_comments=True)

log = logging.getLogger('updatebot.pkgsource')


def loaded(func):
    @wraps(func)
    def wrapper(other, *args, **kwargs):
        if other._loaded:
            return
        return func(other, *args, **kwargs)
    return wrapper


class Package(object):
    __slots__ = ('_pom', '_json', 'arch', 'fullVersion', 'name',
                 'epoch', 'version', 'release', 'location')

    def __init__(self, pom, arch, json=None):
        self._json = json
        self._pom = pom
        self.epoch = '1'
        try:
            self.fullVersion = str(pom.version).strip()
        except AttributeError:
            log.debug("No version set, trying parent project")
            self.fullVersion = str(pom.parent.version).strip()
        self.name = str(pom.artifactId)
        self.arch = arch and arch or ''
        head, _, tail = self.fullVersion.rpartition('-')
        if head and tail:
            self.version = head
            self.release = tail
        elif tail:
            self.version = tail
            self.release = ''
        else:
            raise ValueError("Could not parse maven version into"
                             " version and release")
        self.location = json['downloadUri'] if json else None

    def __repr__(self):
        return '<pomsource.Package(%r, %r, %r)>' % (
            self.name, self.version, self.arch)

    def getConaryVersion(self):
        assert self.arch == 'src'
        return self.fullVersion.replace('-', '_')

    def getBuildRequires(self):
        buildRequires = set()
        if hasattr(self._pom, 'parent'):
            # add parent projects as a build req
            buildRequires.add(str(self._pom.parent.artifactId))

        if hasattr(self._pom, 'dependencies'):
            for dep in self._pom.dependencies.iterchildren():
                if hasattr(dep, 'optional') and dep.optional:
                    # ignore opitonal deps, these are deps a dependent
                    # project may want to include
                    continue

                if hasattr(dep, 'scope') and str(dep.scope) != 'compile':
                    # we only want compile deps (the default)
                    continue

                buildRequires.add(str(dep.artifactId))

        return list(buildRequires)

    def getNevra(self):
        return self.name, self.epoch, self.version, self.release, self.arch


class PomSource(BasePackageSource):
    """
    Creates a map of packages from a pom file
    """

    def __init__(self, cfg, ui):
        BasePackageSource.__init__(self, cfg, ui)

    @loaded
    def load(self):
        auth = self._cfg.artifactoryUser.find(self._cfg.repositoryUrl)

        for repo in self._cfg.repositoryPaths:
            log.info('loading repository data %s' % repo)
            client = artifactory.Client(self._cfg.repositoryUrl, auth)
            archStr = self._cfg.repositoryArch.get(repo, None)
            self.loadFromClient(client, repo, archStr=archStr)

        self._loaded = True

    def loadFromClient(self, client, repo, archStr=None):
        poms = [pom for pom in client.quick_search('pom', repos=repo)
                if pom.get('mimeType') == 'application/x-maven-pom+xml']
        artifacts = client.retrieve_artifact(
            '%(repo)s:%(path)s' % p for p in poms)

        for pom, artifact in zip(poms, artifacts):
            pomObj = objectify.fromstring(artifact.text.encode('utf-8'),
                                          XMLParser)
            if hasattr(pomObj, 'getroot'):
                pomObj = pomObj.getroot()

            artifacts = client.gavc_search(
                group=(str(pomObj.groupId) if hasattr(pomObj, 'groupId') else
                       str(pomObj.parent.groupId)),
                artifact=str(pomObj.artifactId),
                version=(str(pomObj.version) if hasattr(pomObj, 'version') else
                         str(pomObj.parent.version)),
            )
            if not artifacts:
                log.info("No artifacts associated with this pom:"
                          " %(repo)s:%(path)s" % pom)

            srcPkg = Package(pomObj, 'src')
            binPkgs = [Package(pomObj, archStr, a) for a in artifacts]

            self.srcNameMap.setdefault(srcPkg.name, set()).add(srcPkg)
            self.locationMap[srcPkg.location] = srcPkg
            self.srcPkgMap[srcPkg] = binPkgs

            trvSpec = (srcPkg.name, srcPkg.getConaryVersion(), ('x86_64',))
            self.useMap.setdefault(trvSpec, set()).update(set(['x86_64']))

            for binPkg in binPkgs:
                self.binNameMap.setdefault(binPkg.name, set()).add(binPkg)
                self.locationMap[binPkg.location] = binPkg
                self.binPkgMap[binPkg] = srcPkg
