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
Module for parsing primary.xml.gz from the repository metadata.
"""

__all__ = ('PrimaryXml', )

from repomd.packagexml import PackageXmlMixIn
from repomd.errors import UnknownElementError
from repomd.xmlcommon import XmlFileParser, SlotNode

class _Metadata(SlotNode):
    """
    Python representation of primary.xml.gz from the repository metadata.
    """

    __slots__ = ()

    def addChild(self, child):
        """
        Parse children of metadata element.
        """

        if child.getName() == 'package':
            child.type = child.getAttribute('type')
            SlotNode.addChild(self, child)
        else:
            raise UnknownElementError(child)

    def getPackages(self):
        """
        Get a list of all packages contained in primary.xml.gz.
        @return list of repomd.packagexml._Package objects
        """

        return self.getChildren('package')


class PrimaryXml(XmlFileParser, PackageXmlMixIn):
    """
    Handle registering all types for parsing primary.xml.gz.
    """

    def _registerTypes(self):
        """
        Setup databinder to parse xml.
        """

        PackageXmlMixIn._registerTypes(self)
        self._databinder.registerType(_Metadata, name='metadata')
