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

__all__ = ('PatchesXml', )

# import stable api
from rpath_common.xmllib import api1 as xmllib

from patchxml import PatchXml
from xmlcommon import XmlFileParser
from errors import UnknownElementError

class _Patches(xmllib.BaseNode):
    def addChild(self, child):
        if child.getName() == 'patch':
            child.id = child.getAttribute('id')
            child._parser = PatchXml(None, child.location)
            child.parseChildren = child._parser.parse
            xmllib.BaseNode.addChild(self, child)
        else:
            raise UnknownElementError(child)

    def getPatches(self):
        return self.getChildren('patch')


class _PatchElement(xmllib.BaseNode):
    id = None
    checksum = ''
    checksumType = 'sha'
    location = ''

    def addChild(self, child):
        if child.getName() == 'checksum':
            self.checksum = child.finalize()
            self.checksumType = child.getAttribute('type')
        elif child.getName() == 'location':
            self.location = child.getAttribute('href')
        else:
            raise UnkownElementError(child)


class PatchesXml(XmlFileParser):
    def _registerTypes(self):
        self._databinder.registerType(_Patches, name='patches')
        self._databinder.registerType(_PatchElement, name='patch')
        self._databinder.registerType(xmllib.StringNode, name='checksum')
