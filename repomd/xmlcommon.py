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
