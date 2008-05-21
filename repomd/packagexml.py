#
# Copyright (c) 2008 rPath, Inc.
#
# This program is distributed under the terms of the Common Public License,
# version 1.0. A copy of this license should have been distributed with this
# source file in a file called LICENSE. If it is not present, the license
# is always available at http://www.rpath.com/permanent/licenses/CPL-1.0.
#
# This program is distributed in the hope that it will be useful, but
# without any warranty; without even the implied warranty of merchantability
# or fitness for a particular purpose. See the Common Public License for
# full details.
#

__all__ = ('PackageXmlMixIn', )

from rpath_common.xmllib import api1 as xmllib

from errors import UnknownElementError, UnknownAttributeError

class _Package(xmllib.BaseNode):
    name = None
    arch = None
    epoch = None
    version = None
    release = None
    checksum = None
    checksumType = None
    summary = None
    description = None
    packager = None
    url = None
    fileTimestamp = None
    buildTimestamp = None
    packageSize = None
    installedSize = None
    archiveSize = None
    location = None
    license = None
    vendor = None
    group = None
    buildhost = None
    sourcerpm = None
    headerStart = None
    headerEnd = None

    def addChild(self, child):
        if child.getName() == 'name':
            self.name = child.finalize()
        elif child.getName() == 'arch':
            self.arch = child.finalize()
        elif child.getName() == 'version':
            self.epoch = child.getAttribute('epoch')
            self.version = child.getAttribute('ver')
            self.release = child.getAttribute('rel')
        elif child.getName() == 'checksum':
            self.checksum = child.finalize()
            self.checksumType = child.getAttribute('type')
        elif child.getName() == 'summary':
            self.summary = child.finalize()
        elif child.getName() == 'description':
            self.description = child.finalize()
        elif child.getName() == 'packager':
            self.packager = child.finalize()
        elif child.getName() == 'url':
            self.url = child.finalize()
        elif child.getName() == 'time':
            self.fileTimestamp = child.getAttribute('file')
            self.buildTimestamp = child.getAttribute('build')
        elif child.getName() == 'size':
            self.packageSize = child.getAttribute('package')
            self.installedSize = child.getAttribute('installed')
            self.archiveSize = child.getAttribute('archive')
        elif child.getName() == 'location':
            self.location = child.getAttribute('href')
        elif child.getName() == 'format':
            self.format = []
            for node in child.iterChildren():
                if node.getName() == 'rpm:license':
                    self.license = node.getText()
                elif node.getName() == 'rpm:vendor':
                    self.vendor = node.getText()
                elif node.getName() == 'rpm:group':
                    self.group = node.getText()
                elif node.getName() == 'rpm:buildhost':
                    self.buildhost = node.getText()
                elif node.getName() == 'rpm:sourcerpm':
                    self.sourcerpm = node.getText()
                elif node.getName() == 'rpm:header-range':
                    self.headerStart = node.getAttribute('start')
                    self.headerEnd = node.getAttribute('end')
                elif node.getName() in ('rpm:provides', 'rpm:requires',
                                        'rpm:obsoletes', 'rpm:recommends',
                                        'rpm:conflicts', 'suse:freshens'):
                    self.format.append(node)
                elif node.getName() == 'file':
                    pass
                else:
                    raise UnknownElementError(node)
        elif child.getName() == 'pkgfiles':
            pass
        else:
            raise UnknownElementError(child)


class _RpmRequires(xmllib.BaseNode):
    def addChild(self, child):
        if child.getName() in ('rpm:entry', 'suse:entry'):
            for attr, value in child.iterAttributes():
                child.kind = None
                child.name = None
                child.epoch = None
                child.version = None
                child.release = None
                child.flags = None
                child.pre = None

                if attr == 'kind':
                    child.kind = value
                elif attr == 'name':
                    child.name = value
                elif attr == 'epoch':
                    child.epoch = value
                elif attr == 'ver':
                    child.version = value
                elif attr == 'rel':
                    child.release = value
                elif attr == 'flags':
                    child.flags = value
                elif attr == 'pre':
                    child.pre = value
                else:
                    raise UnknownAttributeError(child, attr)
            xmllib.BaseNode.addChild(self, child)
        else:
            raise UnknownElementError(child)


class _RpmRecommends(_RpmRequires):
    pass


class _RpmProvides(_RpmRequires):
    pass


class _RpmObsoletes(_RpmRequires):
    pass


class _RpmConflicts(_RpmRequires):
    pass


class _SuseFreshens(_RpmRequires):
    pass


class PackageXmlMixIn(object):
    def _registerTypes(self):
        self._databinder.registerType(_Package, name='package')
        self._databinder.registerType(xmllib.StringNode, name='name')
        self._databinder.registerType(xmllib.StringNode, name='arch')
        self._databinder.registerType(xmllib.StringNode, name='checksum')
        self._databinder.registerType(xmllib.StringNode, name='summary')
        self._databinder.registerType(xmllib.StringNode, name='description')
        self._databinder.registerType(xmllib.StringNode, name='url')
        # FIXME: really shouldn't need to comment these out
        #self._databinder.registerType(xmllib.StringNode, name='license', namespace='rpm')
        #self._databinder.registerType(xmllib.StringNode, name='vendor', namespace='rpm')
        #self._databinder.registerType(xmllib.StringNode, name='group', namespace='rpm')
        #self._databinder.registerType(xmllib.StringNode, name='buildhost', namespace='rpm')
        #self._databinder.registerType(xmllib.StringNode, name='sourcerpm', namespace='rpm')
        self._databinder.registerType(_RpmRequires, name='requires', namespace='rpm')
        self._databinder.registerType(_RpmRecommends, name='recommends', namespace='rpm')
        self._databinder.registerType(_RpmProvides, name='provides', namespace='rpm')
        self._databinder.registerType(_RpmObsoletes, name='obsoletes', namespace='rpm')
        self._databinder.registerType(_RpmConflicts, name='conflicts', namespace='rpm')
        self._databinder.registerType(_SuseFreshens, name='freshens', namespace='suse')
