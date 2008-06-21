#
# Copryright (c) 2008 rPath, Inc.
#

"""
Module for parsing filelists.xml files from the repository metadata.
"""

__all__ = ('FilelistXml', )

from rpath_common.xmllib import api1 as xmllib

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
        return self.getChildren('package')


class FileListsXml(XmlFileParser, PackageXmlMixIn):
    """
    Handle registering all types for parsing filelists.xml files.
    """

    # R0903 - Too few public methods
    # pylint: disable-msg=R0903

    def _registerTypes(self):
        """
        Setup databinder to parse xml.
        """
        PackageXmlMixIn._registerTypes(self)
        self._databinder.registerType(_FileLists, name='filelists')
