#
# Copyright (c) SAS Institute, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
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
