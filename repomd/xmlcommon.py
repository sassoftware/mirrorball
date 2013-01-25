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
Base module for common super classes for repomd.
"""

__all__ = ('XmlFileParser', 'SlotNode')

from rpath_xmllib import api1 as xmllib

class XmlFileParser(object):
    """
    Base class for handling databinder setup.
    """

    def __init__(self, repository, path):
        self._repository = repository
        self._path = path

        self._databinder = xmllib.DataBinder()
        self._registerTypes()

        self._data = None

    def _registerTypes(self):
        """
        Method stub for sub classes to implement.
        """

    def parse(self):
        """
        Parse an xml file.
        @return sub class xmllib.BaseNode
        """

        # W0212 - Access to a protected member _parser of a client class
        # pylint: disable-msg=W0212

        fn = self._repository.get(self._path)
        data = self._databinder.parseFile(fn)

        for child in data.iterChildren():
            if hasattr(child, '_parser') and child._parser is not None:
                child._parser._repository = self._repository

        return data


class SlotNode(xmllib.BaseNode):
    """
    XML node class that initializes all __slots__ entries to None.
    """

    __slots__ = ()

    def __init__(self, *args, **kw):
        for cls in self.__class__.__mro__:
            if hasattr(cls, '__slots__'):
                for attr in self.__slots__:
                    setattr(self, attr, None)
        xmllib.BaseNode.__init__(self, *args, **kw)
