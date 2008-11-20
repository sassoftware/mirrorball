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
Module for parsing package metadata files.
"""

from aptmd.common import BaseContainer, BaseParser

class _Package(BaseContainer):
    """
    Package container class.
    """

    __slots__ = ('source', 'sourceVersion', 'location', 'summary',
                 'description')


class PackagesParser(BaseParser):
    """
    Package MD Parser class.
    """

    def __init__(self):
        BaseParser.__init__(self)

        self._containerClass = _Package
        self._states.update({
            'installed-size'        : self._keyval,
            'source'                : self._source,
            'replaces'              : self._keyval,
            'depends'               : self._keyval,
            'recommends'            : self._keyval,
            'conflicts'             : self._keyval,
            'filename'              : self._filename,
            'size'                  : self._keyval,
            'md5sum'                : self._keyval,
            'sha1'                  : self._keyval,
            'sha256'                : self._keyval,
            'description'           : self._description,
            'bugs'                  : self._bugs,
            'origin'                : self._keyval,
            'task'                  : self._keyval,
        })

    def parse(self, fn):
        """
        Parse a given file or file like object line by line.
        @param fn: filename or file like object to parse.
        @type fn: string or file like object.
        """

        # Attribute 'description' defined outside __init__
        # pylint: disable-msg=W0201

        ret = BaseParser.parse(self, fn)
        # If there is any text left, collect it in the description
        if self._text:
            self._curObj.description = self._text
            self._text = ''

        return ret

    def _source(self):
        """
        Parse the source line.
        """

        # Attribute 'sourceVersion' defined outside __init__
        # pylint: disable-msg=W0201

        source = self._getLine()
        assert source != ''

        # source in the form "Source: srcName (srcVer)"
        if len(self._line) == 3:
            source = self._line[1]

            srcVer = self._line[2].strip()
            srcVer = srcVer.strip('(')
            srcVer = srcVer.strip(')')

            self._curObj.sourceVersion = srcVer

        self._curObj.source = source

    def _filename(self):
        """
        Parse the filename line.
        """

        # Attribute 'location' defined outside __init__
        # pylint: disable-msg=W0201

        self._curObj.location = self._getLine()

    def _description(self):
        """
        Parse the description line.
        """

        # Attribute 'summary' defined outside __init__
        # pylint: disable-msg=W0201

        self._curObj.summary = self._getLine()

    def _bugs(self):
        """
        Parse the bugs line.
        """

        self._curObj.description = self._text
        self._text = ''
        self._keyval()
