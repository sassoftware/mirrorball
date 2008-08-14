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

import os

from aptmd.common import BaseContainer, BaseParser

class _SourcePackage(BaseContainer):
    __slots__ = ('binaries', 'directory', 'files')


class SourcesParser(BaseParser):

    def __init__(self):
        BaseParser.__init__(self)

        self._containerClass = _SourcePackage
        self._inFiles = False
        self._states.update({
            'architecture'          : self._architecture,
            'binary'                : self._binary,
            'build-depends'         : self._keyval,
            'standards-version'     : self._keyval,
            'format'                : self._keyval,
            'directory'             : self._directory,
            'files'                 : self._files,
            'homepage'              : self._keyval,
            'uploaders'             : self._keyval,
        })

    def _parseLine(self, line):
        BaseParser._parseLine(self, line)

        state = self._getState(self._line[0])
        if state != 'files' and state in self._states:
            self._inFiles = False

        if self._inFiles:
            self._file()

    def _architecture(self):
        self._curObj.arch = 'src'

    def _binary(self):
        self._line[-1] = self._line[-1].strip()
        self._curObj.binaries = [ x.strip(',') for x in self._line[1:] ]

    def _directory(self):
        self._curObj.directory = self._getLine()

    def _files(self):
        self._inFiles = True

    def _file(self):
        if self._curObj.files is None:
            self._curObj.files = []

        path = os.path.join(self._curObj.directory, self._line[2])
        self._curObj.files.append(path)
