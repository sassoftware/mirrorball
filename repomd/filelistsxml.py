#
# Copryright (c) 2008-2009 rPath, Inc.
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
