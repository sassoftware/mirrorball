#
# Copyright (c) 2014 SAS Institute Inc
#

from string import Template
import logging

from lxml import etree


log = logging.getLogger(__name__)


class PomTemplate(Template):
    idpattern = '[_a-z][-_a-z0-9.]*'


class PomObject(object):
    """
    Abstracts away processing pom xml
    """
    def __init__(self, xml, client, repo):
        """
        Create a PomObject from xml string

        :param str xml: xml used to construct the pom object
        :param client: an artifactory client for recursing parent projects
        :type client: artifactory.Client
        """
        self._parent = None
        self._artifactId = None
        self._groupId = None
        self._version = None
        self._properties = None
        self._dependencyManagement = None
        self._dependencies = None

        self._xml = etree.fromstring(xml,
            parser=etree.XMLParser(recover=True, remove_comments=True,
                                   remove_pis=True))
        if None in self._xml.nsmap:
            self._ns = '{%s}' % self._xml.nsmap[None]
        else:
            self._ns = ''

        parent = self._xml.find('%sparent' % self._ns)
        if parent is not None:
            groupId = parent.find('%sgroupId' % self._ns).text.strip()
            artifactId = parent.find('%sartifactId' % self._ns).text.strip()
            version = parent.find('%sversion' % self._ns).text.strip()
            parentArtifacts = client.gavc_search(
                group=groupId,
                artifact=artifactId,
                version=version,
            )
            parentPom = [a for a in parentArtifacts
                         if a.get('mimeType') == 'application/x-maven-pom+xml']
            if parentPom:
                if len(parentPom) > 1:
                    log.warning("Found more than one parent pom file %s",
                        self.artifactId)
                    # try filtering for a parent pom in our repo
                    # otherwise use the first
                    _parentPom = [p for p in parentPom
                                  if p.get('repo') == repo]
                    if _parentPom:
                        parentPom = _parentPom
                parentPom = parentPom[0]
                parentXml = client.retrieve_artifact('%(repo)s:%(path)s' %
                                                     parentPom)
                self._parent = PomObject(parentXml.text.encode('utf8'), client,
                                         repo)
            else:
                # we got here because the parent is not
                # cached in svcartifact
                log.warning('Parent pom of %s is not cached in svcartifact:'
                            ' %s (%s)', self.artifactId, artifactId, version)

    @property
    def artifactId(self):
        if self._artifactId is None:
            artifactId = self._xml.find('%sartifactId' % self._ns).text.strip()
            self._artifactId = self._replaceProperties(artifactId)
        return self._artifactId

    @property
    def groupId(self):
        if self._groupId is None:
            groupId = self._xml.find('%sgroupId' % self._ns)
            if groupId is None:
                groupId = self._xml.find(
                    '%sparent/%sgroupId' % (self._ns, self._ns))
            self._groupId = self._replaceProperties(groupId.text.strip())
        return self._groupId

    @property
    def version(self):
        if self._version is None:
            version = self._xml.find('%sversion' % self._ns)
            if version is None:
                version = self._xml.find(
                    '%sparent/%sversion' % (self._ns, self._ns))
            self._version = self._replaceProperties(version.text.strip())
        return self._version

    @property
    def properties(self):
        if self._properties is None:
            properties = {}
            if self._parent is not None:
                properties.update(self._parent.properties)
                properties['parent.version'] = self._parent.version
            project_properties = self._xml.find('%sproperties' % self._ns)
            if project_properties is not None:
                properties.update(
                    (p.tag.replace('%s' % self._ns, ''), p.text)
                    for p in project_properties.iterchildren())
            self._properties = properties
        return self._properties

    @property
    def dependencyManagement(self):
        if self._dependencyManagement is None:
            dependencyManagement = {}
            if self._parent is not None:
                dependencyManagement.update(self._parent.dependencyManagement)
            for dep in self._xml.iter('dependencyManagement/dependencies'):
                gav, scope, optional = \
                    self._processDependencyElement(dep)
                group, artifact, version = self._processVersion(gav)
                if scope == 'compile' and not optional:
                    dependencyManagement[(group, artifact)] = version
            self._dependencyManagement = dependencyManagement
        return self._dependencyManagement

    @property
    def dependencies(self):
        if self._dependencies is None:
            dependencies = set()
            if self._parent is not None:
                dependencies = self._parent.dependencies
                dependencies.add(self._parent.artifactId)
            for dep in self._xml.iter('dependencies/dependency'):
                artifactId = dep.find('%sartifactId' % self._ns)
                artifactId = artifactId.text.strip()
                dependencies.add(self._replaceProperties(artifactId))
            self._dependencies = dependencies
        return self._dependencies

    def _processDependencyElement(self, dep):
        scope = dep.find('%sscope' % self._ns)
        if scope is not None:
            scope = scope.text
        else:
            scope = 'compile'

        optional = dep.find('%soptional' % self._ns)
        if optional is not None:
            optional = (optional.text == 'true')
        else:
            optional = False

        version = dep.find('%sversion' % self._ns)
        if version is not None:
            version = version.text

        group = dep.find('%sgroupId' % self._ns).text
        artifact = dep.find('%sartifactId' % self._ns).text
        return (group, artifact, version), scope, optional

    def _processVersion(self, gav):
        group, artifact, version = gav
        if version is None:
            if (group, artifact) in self.dependencyManagement:
                version = self.dependencyManagement[(group, artifact)]
            else:
                version = self._parent.version

        version = self._replaceProperties(version)

        return group, artifact, version

    def _replaceProperties(self, string):
        newString = PomTemplate(string).substitute(self.properties)
        return newString


class Package(object):
    __slots__ = ('artifacts', 'arch', 'fullVersion', 'name', 'buildRequires',
                 'epoch', 'version', 'release', 'location',)

    def __init__(self, pom, location, arch='src', artifacts=None):
        self.location = location
        self.artifacts = artifacts if artifacts is not None else []
        self.name = pom.artifactId
        self.epoch = '0'
        self.version = pom.version
        self.release = ''
        self.arch = arch and arch or ''
        self.buildRequires = list(pom.dependencies)

    def __repr__(self):
        return '<pomsource.Package(%r, %r, %r)>' % (
            self.name, self.version, self.arch)

    def getConaryVersion(self):
        return self.version.replace('-', '_')

    def getNevra(self):
        return self.name, self.epoch, self.version, self.release, self.arch

    @property
    def nevra(self):
        return self

    @property
    def checksum(self):
        return None
