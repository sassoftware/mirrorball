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
Module for parsing Sources file from an Apt repository.
"""

import os

from aptmd.common import BaseContainer, BaseParser

class _SourcePackage(BaseContainer):
    """
    Container for source data.
    """

    _slots = ('binaries', 'directory', 'files', 'checksumssha1',
        'checksumssha256')


class SourcesParser(BaseParser):
    """
    Class for parsing Source metadata.
    """

    def __init__(self):
        BaseParser.__init__(self)

        self._containerClass = _SourcePackage
        self._states.update({
            'binary'                : self._binary,
            'build-depends'         : self._keyval,
            'standards-version'     : self._keyval,
            'format'                : self._keyval,
            'directory'             : self._directory,
            'files'                 : self._files,
            '_file'                 : self._file,
            'homepage'              : self._keyval,
            'uploaders'             : self._keyval,
            'checksums-sha1'        : self._sha1,
            '_checksums-sha1'       : self._sha1bucket,
            'checksums-sha256'      : self._sha256,
            '_checksums-sha256'     : self._sha256bucket,
        })

    def _architecture(self):
        """
        Parse architecture.
        """

        # Attribute 'arch' defined outside __init__
        # pylint: disable-msg=W0201

        self._curObj.arch = 'src'

    def _binary(self):
        """
        Parse binary info.
        """

        # Attribute 'binary' defined outside __init__
        # pylint: disable-msg=W0201

        self._line[-1] = self._line[-1].strip()
        self._curObj.binaries = [ x.strip(',') for x in self._line[1:] ]

    def _directory(self):
        """
        Parse directory info.
        """

        # Attribute 'directory' defined outside __init__
        # pylint: disable-msg=W0201

        self._curObj.directory = self._getLine()

    def _files(self):
        """
        Parse files info.
        """

        # Attribute 'files' defined outside __init__
        # pylint: disable-msg=W0201

        self._curObj.files = []
        self._bucketState = '_file'

    def _file(self):
        """
        Parse file info.
        """

        if len(self._line) != 4:
            return

        fileName = self._line[3].strip()
        path = os.path.join(self._curObj.directory, fileName)
        self._curObj.files.append(path)

    def _sha1(self):
        """
        Start of sha1 section.
        """

        self._curObj.checksumssha1 = []
        self._bucketState = '_checksums-sha1'

    def _sha1bucket(self):
        """
        Handle lines of a sha1 section.
        """

        self._curObj.checksumssha1.append(' '.join(self._line[1:]))

    def _sha256(self):
        """
        Start of sha256 section.
        """

        self._curObj.checksumssha256 = []
        self._bucketState = '_checksums-sha256'

    def _sha256bucket(self):
        """
        Handle lines of a sha256 section.
        """

        self._curObj.checksumssha256.append(' '.join(self._line[1:]))
