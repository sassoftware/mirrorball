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
Module for parsing package metadata files.
"""

from aptmd.common import BaseContainer, BaseParser

class _Package(BaseContainer):
    """
    Package container class.
    """

    _slots = ('source', 'sourceVersion', 'location', 'summary',
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
            '_description'          : self._descriptionbucket,
            'bugs'                  : self._keyval,
            'origin'                : self._keyval,
            'task'                  : self._keyval,
        })

    def parse(self, fn, path):
        """
        Parse a given file or file like object line by line.
        @param fn: filename or file like object to parse.
        @type fn: string or file like object.
        @param path: path to the metadata file
        @type path: string
        """

        # Attribute 'description' defined outside __init__
        # pylint: disable-msg=W0201

        ret = BaseParser.parse(self, fn, path)
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
        self._bucketState = '_description'

    def _descriptionbucket(self):
        """
        Handle adding lines of a description.
        """

        prefix = '\n'
        if self._curObj.description is None:
            self._curObj.description = ''
            prefix = ''

        self._curObj.description += prefix
        self._curObj.description += ' '.join(self._line)
