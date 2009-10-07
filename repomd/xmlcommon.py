#
# Copyright (c) 2008 rPath, Inc.
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
            if hasattr(child, '_parser'):
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
