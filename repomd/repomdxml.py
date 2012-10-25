#
# Copyright (c) rPath, Inc.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#


"""
Module for parsing repomd.xml files from the repository metadata.
"""

__all__ = ('RepoMdXml', )

# use stable api
from rpath_xmllib import api1 as xmllib

from repomd.primaryxml import PrimaryXml
from repomd.patchesxml import PatchesXml
from repomd.filelistsxml import FileListsXml
from repomd.updateinfoxml import UpdateInfoXml
from repomd.xmlcommon import XmlFileParser, SlotNode
from repomd.errors import UnknownElementError

class _RepoMd(SlotNode):
    """
    Python representation of repomd.xml from the repository metadata.
    """

    __slots__ = ('revision', 'tags')

    def addChild(self, child):
        """
        Parse children of repomd element.
        """

        # W0212 - Access to a protected member _parser of a client class
        # pylint: disable-msg=W0212

        name = child.getName()
        if name == 'revision':
            self.revision = child.finalize()
        elif name == 'tags':
            # FIXME: Is this complete? -jau
            self.tags = child.finalize()
        elif name == 'data':
            child.type = child.getAttribute('type')
            if child.type == 'patches':
                child._parser = PatchesXml(None, child.location)
                child.parseChildren = child._parser.parse
            elif child.type == 'primary':
                child._parser = PrimaryXml(None, child.location)
                child.parseChildren = child._parser.parse
            elif child.type == 'filelists':
                child._parser = FileListsXml(None, child.location)
                child.parseChildren = child._parser.parse
            elif child.type == 'updateinfo':
                child._parser = UpdateInfoXml(None, child.location)
                child.parseChildren = child._parser.parse
            SlotNode.addChild(self, child)
        else:
            raise UnknownElementError(child)

    def getRepoData(self, name=None):
        """
        Get data elements of repomd xml file.
        @param name: filter by type of node
        @type name: string
        @return list of nodes
        @return single node
        @return None
        """

        if not name:
            return self.getChildren('data')

        for node in self.getChildren('data'):
            if node.type == name:
                return node

        return None


class _RepoMdDataElement(SlotNode):
    """
    Parser for repomd.xml data elements.
    """
    __slots__ = ('location', 'checksum', 'checksumType', 'timestamp',
                 'openChecksum', 'openChecksumType', 'databaseVersion',
                 'size', 'openSize', 'type', '_parser', 'parseChildren', )

    # All attributes are defined in __init__ by iterating over __slots__,
    # this confuses pylint.
    # W0201 - Attribute $foo defined outside __init__
    # pylint: disable-msg=W0201

    def addChild(self, child):
        """
        Parse children of data element.
        """

        name = child.getName()
        if name == 'location':
            self.location = child.getAttribute('href')
        elif name == 'checksum':
            self.checksum = child.finalize()
            self.checksumType = child.getAttribute('type')
        elif name == 'timestamp':
            self.timestamp = child.finalize()
        elif name == 'open-checksum':
            self.openChecksum = child.finalize()
            self.openChecksumType = child.getAttribute('type')
        elif name == 'database_version':
            self.databaseVersion = child.finalize()
        elif name == 'size':
            self.size = child.finalize()
        elif name == 'open-size':
            self.openSize = child.finalize()
        else:
            raise UnknownElementError(child)


class RepoMdXml(XmlFileParser):
    """
    Handle registering all types for parsing repomd.xml file.
    """

    def _registerTypes(self):
        """
        Setup databinder to parse xml.
        """

        self._databinder.registerType(_RepoMd, name='repomd')
        self._databinder.registerType(_RepoMdDataElement, name='data')
        self._databinder.registerType(xmllib.StringNode, name='revision')
        self._databinder.registerType(xmllib.StringNode, name='checksum')
        self._databinder.registerType(xmllib.IntegerNode, name='timestamp')
        self._databinder.registerType(xmllib.StringNode, name='open-checksum')
        self._databinder.registerType(xmllib.StringNode, name='database_version')
