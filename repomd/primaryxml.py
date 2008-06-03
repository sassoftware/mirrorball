#
# Copryright (c) 2008 rPath, Inc.
#

"""
Module for parsing primary.xml.gz from the repository metadata.
"""

__all__ = ('PrimaryXml', )

from rpath_common.xmllib import api1 as xmllib

from repomd.xmlcommon import XmlFileParser
from repomd.packagexml import PackageXmlMixIn
from repomd.errors import UnknownElementError

class _Metadata(xmllib.BaseNode):
    """
    Python representation of primary.xml.gz from the repository metadata.
    """

    def addChild(self, child):
        """
        Parse children of metadata element.
        """

        if child.getName() == 'package':
            child.type = child.getAttribute('type')
            xmllib.BaseNode.addChild(self, child)
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

    # R0903 - Too few public methods
    # pylint: disable-msg=R0903

    def _registerTypes(self):
        """
        Setup databinder to parse xml.
        """

        PackageXmlMixIn._registerTypes(self)
        self._databinder.registerType(_Metadata, name='metadata')
