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
Module for parsing patches.xml from the repository metadata.
"""

__all__ = ('PatchesXml', )

# import stable api
from rpath_xmllib import api1 as xmllib

from repomd.patchxml import PatchXml
from repomd.xmlcommon import XmlFileParser, SlotNode
from repomd.errors import UnknownElementError

class _Patches(SlotNode):
    """
    Python representation of patches.xml from the repository metadata.
    """

    __slots__ = ()

    def addChild(self, child):
        """
        Parse children of patches element.
        """

        # W0212 - Access to a protected member _parser of a client class
        # pylint: disable-msg=W0212

        if child.getName() == 'patch':
            child.id = child.getAttribute('id')
            child._parser = PatchXml(None, child.location)
            child.parseChildren = child._parser.parse
            SlotNode.addChild(self, child)
        else:
            raise UnknownElementError(child)

    def getPatches(self):
        """
        Get a list of all patches in the repository.
        @return list of _PatchElement instances
        """

        return self.getChildren('patch')


class _PatchElement(SlotNode):
    """
    Parser for patch element of patches.xml.
    """

    __slots__ = ('id', 'checksum', 'checksumType', 'location', '_parser',
        'parseChildren')

    # All attributes are defined in __init__ by iterating over __slots__,
    # this confuses pylint.
    # W0201 - Attribute $foo defined outside __init__
    # pylint: disable-msg=W0201

    def addChild(self, child):
        """
        Parse children of patch element.
        """

        if child.getName() == 'checksum':
            self.checksum = child.finalize()
            self.checksumType = child.getAttribute('type')
        elif child.getName() == 'location':
            self.location = child.getAttribute('href')
        else:
            raise UnknownElementError(child)


class PatchesXml(XmlFileParser):
    """
    Handle registering all types for parsing patches.xml.
    """

    def _registerTypes(self):
        """
        Setup databinder to parse xml.
        """

        self._databinder.registerType(_Patches, name='patches')
        self._databinder.registerType(_PatchElement, name='patch')
        self._databinder.registerType(xmllib.StringNode, name='checksum')
