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
