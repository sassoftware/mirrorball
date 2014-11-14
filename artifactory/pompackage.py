#
# Copyright (c) 2014 SAS Institute Inc
#

import logging
import os
import re

from lxml import etree


PROPERTY_RE = re.compile(r'\$\{(.*?)\}')

log = logging.getLogger(__name__)


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
        self._project = etree.fromstring(xml,
            parser=etree.XMLParser(recover=True, remove_comments=True,
                                   remove_pis=True))
        if None in self._project.nsmap:
            self._ns = '{%s}' % self._project.nsmap[None]
        else:
            self._ns = ''

        parent = self._project.find('%sparent' % self._ns)
        if parent is not None:
            parentArtifacts = client.gavc_search(
                group=parent.find('%sgroupId' % self._ns).text,
                artifact=parent.find('%sartifactId' % self._ns).text,
                version=parent.find('%sversion' % self._ns).text,
            )
            parentPom = [a for a in parentArtifacts if
                         a.get('mimeType') == 'application/x-maven-pom+xml'][0]
            parentXml = client.retrieve_artifact(
                '{repo}:{path}'.format(**parentPom))
            parent = PomObject(parentXml.text.encode('utf8'), client, repo)
        self._parent = parent
        self._artifactId = None
        self._groupId = None
        self._version = None
        self._properties = None
        self._dependencyManagement = None
        self._dependencies = None

    def __getattribute__(self, name):
        if name.startswith('_'):
            # don't override _-prefixed attrs
            return super(PomObject, self).__getattribute__(name)

        if not hasattr(self, '_' + name):
            raise AttributeError('%s has not attribute %s' %
                (self.__class__.__name__, name))

        getter = getattr(self, '_get_' + name)
        attribute = getattr(self, '_' + name)
        if attribute is None:
            attribute = getter()
        return attribute

    def _get_artifactId(self):
        artifactId = self._project.find('%sartifactId' % self._ns).text
        match = PROPERTY_RE.match(artifactId)
        if match:
            (prop, ) = match.groups()
            value = self.properties.get(prop)
            artifactId = artifactId.replace(prop, value)
        return artifactId

    def _get_groupId(self):
        groupId = self._project.find('%sgroupId' % self._ns)
        if groupId is not None:
            groupId = groupId.text
        else:
            groupId = self._parent.groupId

        match = PROPERTY_RE.match(groupId)
        if match:
            (prop, ) = match.groups()
            value = self.properties.get(prop)
            groupId = groupId.replace(prop, value)
        return groupId

    def _get_version(self):
        version = self._project.find('%sversion' % self._ns)
        if version is not None:
            version = version.text
        else:
            version = self._parent.version

        match = PROPERTY_RE.match(version)
        if match:
            (prop, ) = match.groups()
            version = self.properties.get(prop)
        return version

    def _get_properties(self):
        properties = self._parent.properties if self._parent is not None else {}
        properties.udpate((p.tag.replace('%s' % self._ns, ''), p.text)
                          for p in self._project.iter('properties/property'))
        return properties

    def _get_dependencyManagement(self):
        dependencyManagement = {}
        if self._parent is not None:
            dependencyManagement.update(self._parent.dependencyManagement)
        for dep in self._project.iter('dependencyManagement/dependencies'):
            gav, scope, optional = \
                self._processDependencyElement(dep)
            group, artifact, version = self._processVersion(gav)
            if scope == 'compile' and not optional:
                dependencyManagement[(group, artifact)] = version
        return dependencyManagement

    def _get_dependencies(self):
        dependencies = set()
        if self._parent is not None:
            dependencies = self._parent.dependencies
            dependencies.add(self._parent.artifactId)
        for dep in self._project.iter('dependencies/dependency'):
            dependencies.add(dep.find('%sartifactId' % self._ns).text.strip())
        return dependencies


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
        if gav[1] == 'spring-context':
            import epdb; epdb.set_trace()  # XXX BREAKPOINT
        group, artifact, version = gav
        if version is None:
            if (group, artifact) in self.dependencyManagement:
                version = self.dependencyManagement[(group, artifact)]
            else:
                version = self._parent.version

        match = PROPERTY_RE.match(version)
        if match:
            (prop, ) = match.groups()
            version = self.properties.get(prop)

        return group, artifact, version


class Package(object):
    __slots__ = ('artifact', 'arch', 'fullVersion', 'name', 'buildRequires',
                 'epoch', 'version', 'release', 'location',)

    def __init__(self, pom, location, arch='src', artifact=None):
        self.location = location
        self.artifact = artifact
        self.name = pom.artifactId.strip()
        self.epoch = '0'
        self.version = pom.version.strip()
        self.release = ''
        self.arch = arch and arch or ''
        self.buildRequires = list(pom.dependencies)

    def __repr__(self):
        if self.arch == 'src':
            return '<pomsource.Package(%r, %r, %r)>' % (
                self.name, self.version, self.arch)
        return '<pomsource.Package(%r, %r, %r, %r)>' % (
            self.name,
            self.version,
            self.arch,
            '%(repo)s:%(path)s' % self.artifact,
        )

    def getConaryVersion(self):
        assert self.arch == 'src'
        return self.version.replace('-', '_')

    def getNevra(self):
        return self.name, self.epoch, self.version, self.release, self.arch

    @property
    def nevra(self):
        return self

    @property
    def checksum(self):
        return None
