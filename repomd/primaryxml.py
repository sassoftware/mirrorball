#
# Copryright (c) 2008 rPath, Inc.
#

__all__ = ('PrimaryXml', )

from rpath_common.xmllib import api1 as xmllib

from packagexml import *
from xmlcommon import XmlFileParser
from errors import UnknownElementError

class _Metadata(xmllib.BaseNode):
    def addChild(self, child):
        if child.getName() == 'package':
            child.type = child.getAttribute('type')
            xmllib.BaseNode.addChild(self, child)
        else:
            raise UnknownElementError(child)

    def getPackages(self):
        return self.getChildren('package')


class PrimaryXml(XmlFileParser, PackageXmlMixIn):
    def _registerTypes(self):
        PackageXmlMixIn._registerTypes(self)
        self._databinder.registerType(_Metadata, name='metadata')
