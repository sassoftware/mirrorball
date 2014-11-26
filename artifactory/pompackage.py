#
# Copyright (c) 2014 SAS Institute Inc
#

from string import Template
import logging


log = logging.getLogger(__name__)


class PomTemplate(Template):
    idpattern = '[_a-z][-_a-z0-9.]*'


class PomPackage(object):
    """Abstracts away processing pom xml
    """
    __slots__ = ('_dependencies', '_dependencyManagement', '_ns', '_parent',
                 '_properties', '_xml', 'arch', 'artifactId', 'artifacts',
                 'buildRequires', 'children', 'groupId', 'location', 'name',
                 'version',)

    def __init__(self, gav, resource, xml, parent, artifacts=None, arch=None):
        """
        Create a PomPackage

        @param gav: group, artifact, version
        @type gav: tuple
        @param resource: artifactory json resource for pom file
        @type pomResource: dict
        @param xml: pom file xml
        @type xml: lxml.ElementTree
        @param parent: parent project package
        @type parent: PomPackage
        @param arch: architecture string, x86 or x86_64
        @type arch: str
        """
        self._properties = None
        self._dependencyManagement = None
        self._dependencies = None

        self._xml = xml
        self._ns = ('{%s}' % xml.nsmap[None]) if None in xml.nsmap else ''
        self._parent = parent
        if parent and self not in parent.children:
            parent.children.append(self)

        self.groupId, self.artifactId, self.version = gav
        self.location = '%(repo)s:%(path)s' % resource
        self.artifacts = artifacts if artifacts is not None else []
        self.arch = arch if arch is not None else ''
        self.buildRequires = [d[1] for d in self.dependencies]
        self.children = []

    def __repr__(self):
        return '<pomsource.Package(%r, %r, %r)>' % self.getGAV()

    @property
    def epoch(self):
        return '0'

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
    def nevra(self):
        return self

    @property
    def checksum(self):
        return None

    @property
    def name(self):
        return str(self.artifactId)

    @property
    def properties(self):
        if self._properties is None:
            properties = {}
            if self._parent is not None:
                properties.update(self._parent.properties)
                properties['parent.groupId'] = self._parent.groupId
                properties['parent.version'] = self._parent.version
            project_properties = self._xml.find('%sproperties' % self._ns)
            if project_properties is not None:
                properties.update(
                    (p.tag.replace('%s' % self._ns, ''), p.text.strip())
                     for p in project_properties.iterchildren())
            properties['project.groupId'] = self.groupId
            properties['project.version'] = self.version
            self._properties = properties
        return self._properties

    @property
    def dependencyManagement(self):
        if self._dependencyManagement is None:
            dependencyManagement = {}
            if self._parent is not None:
                dependencyManagement.update(self._parent.dependencyManagement)
            depManagmentString = ('{0}dependencyManagement/{0}dependencies'
                                  '/{0}dependency'.format(self._ns))
            for dep in self._xml.findall(depManagmentString):
                gav, scope, optional = self._processDependencyElement(dep)
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
                dependencies.add(self._parent.getGAV())

            for dep in self._xml.findall('{0}dependencies/{0}dependency'):
                (group, artifact, version), scope, optional = \
                    self._processDependencyElement(dep)
                if version is None:
                    version = self.dependencyManagement[(group, artifact)]
                dependencies.add((group, artifact, version))
            self._dependencies = dependencies
        return self._dependencies

    def _processDependencyElement(self, dep):
        """Process the xml element and pull out the group, artifact, version,
        scope and optionality of the dependency.

        @param dep: a dependency elemnent from a pom file
        @type dep: lxml.etree.Element
        @return: ((group, artifact, version), scope, optional)
        @rtype: tuple
        """
        group = dep.find('%sgroupId' % self._ns).text.strip()
        group = self._replaceProperties(group)

        artifact = dep.find('%sartifactId' % self._ns).text.strip()
        artifact = self._replaceProperties(artifact)

        version = dep.find('%sversion' % self._ns)
        if version is not None:
            version = version.text.strip()
        else:
            version = None

        scope = dep.find('%sscope' % self._ns)
        if scope is not None:
            scope = scope.text.strip()
        else:
            scope = 'compile'

        optional = dep.find('%soptional' % self._ns)
        if optional is not None:
            optional = (optional.text.strip() == 'true')
        else:
            optional = False

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
