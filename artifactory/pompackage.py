#
# Copyright (c) 2014 SAS Institute Inc
#

import logging
import re

from lxml import etree

POM_PARSER = etree.XMLParser(recover=True, remove_comments=True,
                             remove_pis=True)
PROPERTY_RE = re.compile(r'\$\{(.*?)\}')
STRIP_NAMESPACE_RE = re.compile(r"<project(.|\s)*?>")


log = logging.getLogger(__name__)


class PomPackage(object):
    """Abstracts away processing pom xml
    """
    __slots__ = ('dependencies', 'dependencyManagement', 'parent', 'properties',
                 'artifactId', 'artifacts', 'children', 'groupId', 'location',
                 'version',)

    def __init__(self, pomEtree, location, client, cache):
        """
        Create a PomPackage

        @param pomEtree: pom
        @type pomEtree: lxml.ElementTree
        @param location: location string
        @type location: str
        @param parent: parent project
        @type parent: PomPackage or None
        @param artifacts: artifacts associated with this project
        @type artifacts: list of json objects or None
        @param arch: architecture string
        @type arch: str or None
        """
        self.location = location

        self.dependencies = []
        self.dependencyManagement = {}
        self.parent = None
        self.properties = {}
        self.artifactId = None
        self.groupId = None
        self.version = None
        self.artifacts = []
        self.children = []

        self.setParent(pomEtree, client, cache)

        self.setProperties(pomEtree)

        self.setArtifactId(pomEtree)
        self.setGroupId(pomEtree)
        self.setVersion(pomEtree)

        self.setDependencyManagement(pomEtree, client, cache)

        self.setArtifacts((self.groupId, self.artifactId, self.version), client)

    def __repr__(self):
        return '<pomsource.Package(%r, %r, %r)>' % self.getGAV()

    def _constructPath(self, groupId, artifactId, version):
        path = '/{0}/{1}/{2}/{1}-{2}.pom'.format(
            groupId.replace('.', '/'),
            artifactId,
            version,
            )
        return path

    def _createPomPackage(self, groupId, artifactId, version, client,
                          cache=None):
        if cache and (groupId, artifactId, version) in cache:
            pom = cache[(groupId, artifactId, version)]
        else:
            path = self._constructPath(groupId, artifactId, version)
            for repo in client._cfg.repositoryPaths:
                location = '%s:%s' % (repo, path)
                pom = client.retrieve_artifact(location)
                if pom is not None:
                    break

            if pom is not None:
                pomEtree = etree.fromstring(
                    STRIP_NAMESPACE_RE.sub('<project>', pom, 1),
                    parser=POM_PARSER,
                    )
                pom = PomPackage(pomEtree, location, client, cache)
                if cache:
                    cache[(groupId, artifactId, version)] = pom
                pom.setDependencies(pomEtree, client, cache)
        return pom

    def _processVersion(self, gav):
        group, artifact, version = gav
        if version is None:
            if (group, artifact) in self.dependencyManagement:
                version = self.dependencyManagement[(group, artifact)]
            else:
                version = self.parent.version

        version = self._replaceProperties(version)

        return group, artifact, version

    def _replaceProperties(self, text, properties=None):
        if properties is None:
            properties = self.properties

        def subfunc(matchobj):
            key = matchobj.group(1)
            if key in properties:
                return properties[key]
            else:
                return matchobj.group(0)

        return PROPERTY_RE.sub(subfunc, text)

    @property
    def checksum(self):
        return None

    @property
    def epoch(self):
        return '0'

    @property
    def buildRequires(self):
        return [d.name for d in self.dependencies]

    @property
    def release(self):
        return ''

    def getConaryVersion(self):
        return str(self.version.replace('-', '_'))

    def getGAV(self):
        return self.groupId, self.artifactId, self.version

    def getNevra(self):
        return self.name, self.epoch, self.version, self.release, self.arch

    @property
    def name(self):
        return str(self.artifactId)

    @property
    def nevra(self):
        return self

    def setArtifactId(self, pom):
        artifactId = self._replaceProperties(pom.findtext('artifactId'))
        self.artifactId = artifactId

    def setArtifacts(self, gavc, client):
        for repo in client._cfg.repositoryPaths:
            artifacts = list(client.gavc_search(*gavc, repos=repo))
            if artifacts:
                break

        if not artifacts:
            raise Exception('No artifacts associated with %s', '/'.join(gavc))

        self.artifacts = artifacts

    def setGroupId(self, pom):
        groupId = pom.findtext('groupId')
        if groupId is None:
            groupId = pom.findtext('parent/groupId')
        groupId = self._replaceProperties(groupId)
        self.groupId = groupId

    def setDependencies(self, pom, client, cache=None):
        depMgmt = self.dependencyManagement

        dependencies = []

        p = self.parent
        while p is not None:
            dependencies.append(p)
            p = p.parent

        dependency_elems = pom.findall('dependencies/dependency')
        for dep in dependency_elems:
            groupId = self._replaceProperties(dep.findtext('groupId'))
            artifactId = self._replaceProperties(dep.findtext('artifactId'))
            version = dep.findtext('version')
            if version is not None:
                version = self._replaceProperties(version)

            scope = dep.findtext('scope')
            optional = dep.findtext('optional')

            # process compile deps
            if optional is None or optional == 'false':
                if version is None:
                    version = depMgmt[(groupId, artifactId)][0]
                    version = self._replaceProperties(version)

                if scope is None:
                    if (groupId, artifactId) in depMgmt:
                        scope = depMgmt[(groupId, artifactId)][1]

                if scope in (None, 'compile', 'import'):
                    dep_pom = self._createPomPackage(
                        groupId, artifactId, version, client, cache)
                    if dep_pom is not None:
                        dependencies.append(dep_pom)
                    else:
                        log.warning(
                            "Dependency of %s is missing: %s",
                            '/'.join(self.getGAV()),
                            '/'.join([groupId, artifactId, version]),
                            )
        self.dependencies = dependencies

    def setDependencyManagement(self, pom, client, cache=None):
        dependencyManagement = {}
        if self.parent is not None:
            dependencyManagement.update(self.parent.dependencyManagement)

        dependencyManagementDependencies = pom.findall(
            'dependencyManagement/dependencies/dependency')
        for dep in dependencyManagementDependencies:
            groupId = self._replaceProperties(dep.findtext('groupId'))
            artifactId = self._replaceProperties(dep.findtext('artifactId'))
            version = self._replaceProperties(dep.findtext('version'))

            scope = dep.findtext('scope')
            if scope is not None and scope == 'import':
                import_pom = self._createPomPackage(groupId, artifactId,
                                                    version, client, cache)
                if import_pom is not None:
                    dependencyManagement.update(import_pom.dependencyManagement)
                else:
                    log.warning('%s missing import pom: %s',
                                '/'.join(self.getGAV()),
                                '/'.join([groupId, artifactId, version]))
            else:
                dependencyManagement[(groupId, artifactId)] = (version, scope)
        self.dependencyManagement = dependencyManagement

    def setParent(self, pom, client, cache=None):
        parent_pom = None
        parent = pom.find('parent')
        if parent is not None:
            groupId = parent.findtext('groupId')
            artifactId = parent.findtext('artifactId')
            version = parent.findtext('version')

            parent_pom = self._createPomPackage(groupId, artifactId, version,
                                                client, cache)
            if parent_pom is None:
                log.warning(
                    'Parent of %s is missing: %s',
                    '/'.join([
                        pom.findtext('groupId') or groupId,
                        pom.findtext('artifactId'),
                        pom.findtext('version') or version,
                        ]),
                    '/'.join([groupId, artifactId, version]),
                    )
        self.parent = parent_pom

    def setProperties(self, pom):
        properties = {}
        project_properties = pom.find('properties')
        if project_properties is not None:
            for prop in project_properties.iterchildren():
                if prop.tag == 'property':
                    name = prop.get('name')
                    value = prop.get('value')
                else:
                    name = prop.tag
                    value = prop.text
                properties[name] = value

        if self.parent is not None:
            properties.update(self.parent.properties)
            properties['parent.groupId'] = self.parent.groupId
            properties['parent.artifactId'] = self.parent.artifactId
            properties['parent.version'] = self.parent.version


        # maven built-in properties
        artifactId = pom.findtext('artifactId')
        groupId = pom.findtext('groupId')
        if groupId is None:
            groupId = pom.findtext('parent/groupId')
        version = pom.findtext('version')
        if version is None:
            version = pom.findtext('parent/version')

        # built-in properties
        properties['version'] = version
        properties['project.artifactId'] = artifactId
        properties['project.groupId'] = groupId
        properties['project.version'] = version
        properties['pom.artifactId'] = artifactId
        properties['pom.groupId'] = groupId
        properties['pom.version'] = version

        self.properties = properties

    def setVersion(self, pom):
        version = pom.findtext('version')
        if version is None:
            version = pom.findtext('parent/version')
        version = self._replaceProperties(version)
        self.version = version
