#
# Copyright (c) 2014 SAS Institute Inc
#

import logging
import re

from lxml import etree

from . import errors
from .versioning import Version, VersionRange


POM_PARSER = etree.XMLParser(
    recover=True,
    remove_comments=True,
    remove_pis=True,
    )
PROPERTY_RE = re.compile(r'\$\{(.*?)\}')
STRIP_NAMESPACE_RE = re.compile(r"<project(.|\s)*?>")


log = logging.getLogger(__name__)


def createPomPackage(groupId, artifactId, version, client,
                     cache=None):
    """Create a PomPackage object for the artifact `groupId:artifactId:version`

    :param str groupId: group identifier
    :param str artifactId: artifact identifier
    :param str version: artifact version
    :param MavenClient client: a maven client
    :param dict cache: optional package cache
    """
    if cache is not None and (groupId, artifactId, version) in cache:
        pom = cache[(groupId, artifactId, version)]
    else:
        path = client.constructPath(groupId, artifactId, version)
        location = 'repo:%s' % path
        pom = client.retrieve_artifact(location)
        if pom is not None:
            pomEtree = etree.fromstring(
                STRIP_NAMESPACE_RE.sub('<project>', pom, 1),
                parser=POM_PARSER,
                )
            pom = PomPackage(pomEtree, location, client, cache)
            if cache is not None:
                cache[(groupId, artifactId, version)] = pom
            pom.setDependencies(pomEtree, client, cache)
        else:
            raise errors.MissingProjectError(
                project=':'.join([groupId, artifactId, version]),
                )
    return pom


def pickVersion(spec, availableVersions):
    """Pick a version from availableVersions according to the range versionRange

    If spec contains a '+', then it is a gradle dyanmic version, and we return
    the newest version in `availableVersions` that starts with `spec`.

    Otherwise, convert spec into maven version range and return the first
    version in availableVersions that is within the range.

    :param str spec: a maven version range spec or gradle dynamic version
    :param availableVersions: list of available versions for this artifact
    :type availableVersions: [artifactory.versioning.Version, ...]
    :return: the newest version that matches the spec
    :rtype: str or None
    """
    if '+' in spec:
        # this is a gradle dynamic version
        for version in availableVersions:
            if str(version).startswith(spec[:-1]):
                return str(version)
    else:
        versionRange = VersionRange.fromstring(spec)
        for version in sorted(availableVersions, reverse=True):
            if version in versionRange:
                return str(version)


class PomPackage(object):
    """Abstracts away processing pom xml
    """
    __slots__ = ('dependencies', 'dependencyManagement', 'parent', 'properties',
                 'artifactId', 'artifacts', 'children', 'groupId', 'location',
                 'version',)

    def __init__(self, pomEtree, location, client, cache):
        """
        Create a PomPackage

        :param pomEtree: pom
        :type pomEtree: lxml.ElementTree
        :param location: location string
        :type location: str
        :param parent: parent project
        :type parent: PomPackage or None
        :param artifacts: artifacts associated with this project
        :type artifacts: list of json objects or None
        :param arch: architecture string
        :type arch: str or None
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

    def __str__(self):
        return ':'.join(self.getGAV())

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
        return str("__".join([self.groupId, self.artifactId]))

    @property
    def nevra(self):
        return self

    def setArtifactId(self, pom):
        artifactId = self._replaceProperties(pom.findtext('artifactId'))
        self.artifactId = artifactId

    def setArtifacts(self, gavc, client):
        self.artifacts = [dict(
            downloadUri=client.artifactUrl(*gavc),
            path=client.constructPath(*gavc),
            )]
        if client.checkJar(*gavc):
            self.artifacts.append(dict(
                downloadUri=client.artifactUrl(*gavc, extension='jar'),
                path=client.constructPath(*gavc, extension='jar'),
                ))

    def setGroupId(self, pom):
        groupId = pom.findtext('groupId')
        if groupId is None:
            groupId = pom.findtext('parent/groupId')
        groupId = self._replaceProperties(groupId)
        self.groupId = groupId

    def setDependencies(self, pom, client, cache=None):
        depMgmt = self.dependencyManagement

        dependencies = set()

        p = self.parent
        while p is not None:
            dependencies.add(p)
            p = p.parent

        # process actual dependencies
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
                    if (any(ch in version for ch in ('+', '[', '(', ']', ')'))
                            or 'latest.' in version):
                        # fetch the maven metadata file
                        path = client.constructPath(
                            groupId,
                            artifactId,
                            artifactName='maven-metadata',
                            extension='xml',
                            )
                        mavenMetadata = client.retrieve_artifact(
                            'repo:%s' % path)
                        if mavenMetadata is not None:
                            mavenMetadata = etree.fromstring(mavenMetadata)
                            if version == 'latest.release':
                                version = mavenMetadata.findtext('release')
                            elif version == 'latest.integration':
                                version = mavenMetadata.findtext('latest')
                            else:
                                versions = [Version(v.text.strip())
                                            for v in mavenMetadata.findall(
                                                "versioning/versions/version")]
                                version = pickVersion(version, versions)
                                if version is None:
                                    raise errors.ArtifactoryError(
                                        "No vaild versions for this range")
                        else:
                            raise RuntimeError("Cannot find maven-metadata.xml"
                                               " for project %s" % self)
                    try:
                        dep_pom = createPomPackage(
                            groupId, artifactId, version, client, cache)
                    except errors.MissingProjectError:
                        log.warning('%s missing dependent project: %s',
                            ':'.join(self.getGAV()),
                            ':'.join([groupId, artifactId, version]),
                            )
                    else:
                        dependencies.add(dep_pom)

        # process depMgmt dependencies to find imports
        dependencyManagementDependencies = pom.findall(
            'dependencyManagement/dependencies/dependency')
        for dep in dependencyManagementDependencies:
            groupId = self._replaceProperties(dep.findtext('groupId'))
            artifactId = self._replaceProperties(dep.findtext('artifactId'))
            version = self._replaceProperties(dep.findtext('version'))

            scope = dep.findtext('scope')
            if scope is not None and scope == 'import':
                try:
                    import_pom = createPomPackage(groupId, artifactId, version,
                                                client, cache)
                except errors.MissingProjectError:
                    log.warning('%s missing import project: %s',
                        ':'.join(self.getGAV()),
                        ':'.join([groupId, artifactId, version]),
                        )
                else:
                    dependencies.add(import_pom)

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
                try:
                    import_pom = createPomPackage(groupId, artifactId, version,
                                                client, cache)
                except errors.MissingProjectError:
                    log.warning('%s missing import project: %s',
                        ':'.join(self.getGAV()),
                        ':'.join([groupId, artifactId, version]),
                        )
                dependencyManagement.update(import_pom.dependencyManagement)
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

            try:
                parent_pom = createPomPackage(groupId, artifactId, version,
                                              client, cache)
            except errors.MissingProjectError:
                log.warning('%s missing parent project: %s',
                    ':'.join([
                        pom.findtext('groupId') or groupId,
                        pom.findtext('artifactId'),
                        pom.findtext('version') or version,
                        ]),
                    ':'.join([groupId, artifactId, version]),
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
