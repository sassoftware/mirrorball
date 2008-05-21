#
# Copryright (c) 2008 rPath, Inc.
#

__all__ = ('PatchXml', )

from rpath_common.xmllib import api1 as xmllib

from packagexml import *
from xmlcommon import XmlFileParser
from errors import UnknownElementError

class _Patch(xmllib.BaseNode):
    name = None
    summary = None
    description = None
    version = None
    release = None
    requires = None
    recommends = None
    rebootNeeded = False
    licenseToConfirm = None
    packageManager = False
    category = None

    def addChild(self, child):
        if child.getName() == 'yum:name':
            self.name = child.finalize()
        elif child.getName() == 'summary':
            if child.getAttribute('lang') == 'en':
                self.summary = child.finalize()
        elif child.getName() == 'description':
            if child.getAttribute('lang') == 'en':
                self.description = child.finalize()
        elif child.getName() == 'yum:version':
            self.version = child.getAttribute('ver')
            self.release = child.getAttribute('rel')
        elif child.getName() == 'rpm:requires':
            self.requires = child.getChildren('entry', namespace='rpm')
        elif child.getName() == 'rpm:recommends':
            self.recommneds = child.getChildren('entry', namespace='rpm')
        elif child.getName() == 'reboot-needed':
            self.rebootNeeded = True
        elif child.getName() == 'license-to-confirm':
            self.licenseToConfirm = child.finalize()
        elif child.getName() == 'package-manager':
            self.packageManager = True
        elif child.getName() == 'category':
            self.category = child.finalize()
        elif child.getName() == 'atoms':
            self.packages = child.getChildren('package')
        else:
            raise UnknownElementError(child)

    def __cmp__(self, other):
        if self.version > other.version:
            return 1
        elif self.version < other.version:
            return -1
        elif self.release > other.release:
            return 1
        elif self.release < other.release:
            return -1
        else:
            return 0


class _Atoms(xmllib.BaseNode):
    def addChild(self, child):
        if child.getName() == 'package':
            child.type = child.getAttribute('type')
            xmllib.BaseNode.addChild(self, child)
        elif child.getName() == 'message':
            pass
        elif child.getName() == 'script':
            pass
        else:
            raise UnknownElementError(child)


class PatchXml(XmlFileParser, PackageXmlMixIn):
    def _registerTypes(self):
        PackageXmlMixIn._registerTypes(self)
        self._databinder.registerType(_Patch, name='patch')
        self._databinder.registerType(xmllib.StringNode, name='name', namespace='yum')
        self._databinder.registerType(xmllib.StringNode, name='category')
        self._databinder.registerType(_Atoms, name='atoms')
        self._databinder.registerType(xmllib.StringNode, name='license-to-confirm')
