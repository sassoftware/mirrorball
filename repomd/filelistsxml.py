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
Module for parsing filelists.xml files from the repository metadata.
"""

__all__ = ('FilelistXml', )

from repomd.xmlcommon import XmlFileParser, SlotNode
from repomd.packagexml import PackageXmlMixIn

class _FileLists(SlotNode):
    """
    Python representation of filelists.xml from the repository metadata.
    """

    __slots__ = ()

    def addChild(self, child):
        """
        Parse children of filelists element.
        """

        if child.getName() == 'package':
            child.name = child.getAttribute('name')
            child.arch = child.getAttribute('arch')
        SlotNode.addChild(self, child)

    def getPackages(self):
        """
        Get package objects with file information.
        """

        return self.getChildren('package')


class FileListsXml(XmlFileParser, PackageXmlMixIn):
    """
    Handle registering all types for parsing filelists.xml files.
    """

    def _registerTypes(self):
        """
        Setup databinder to parse xml.
        """

        PackageXmlMixIn._registerTypes(self)
        self._databinder.registerType(_FileLists, name='filelists')
