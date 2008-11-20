#
# Copryright (c) 2008 rPath, Inc.
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
