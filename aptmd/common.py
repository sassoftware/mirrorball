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

from aptmd.parser import Parser
from aptmd.container import Container

class BaseContainer(Container):
    __slots__ = ('name', 'arch', 'version', 'release')

    def __hash__(self):
        return hash((self.name, self.arch, self.version, self.release))


class BaseParser(Parser):
    def __init__(self):
        Parser.__init__(self)

        self._containerClass = BaseContainer
        self._objects = []

        self._states.update({
            'package'               : self._package,
            'architecture'          : self._architecture,
            'version'               : self._version,
            'priority'              : self._keyval,
            'section'               : self._keyval,
            'maintainer'            : self._keyval,
            'original-maintainer'   : self._keyval,
        })

    def parse(self, fileObj):
        self._objects = []
        Parser.parse(self, fileObj)
        return self._objects

    @staticmethod
    def _getState(key):
        if key.endswith(':'):
            key = key[:-1]
        return key.lower()

    def _package(self):
        if self._curObj is not None:
            if hasattr(self._curObj, 'finalize'):
                self._curObj.finalize()
            self._objects.append(self._curObj)
        self._curObj = self._containerClass()
        self._curObj.name = self._getLine()

    def _architecture(self):
        arch = self._getLine()
        assert arch in ('all', 'i386', 'x86_64')
        self._curObj.arch = arch

    def _version(self):
        debVer = self._getLine()
        if '-' in debVer:
            sdebVer = debVer.split('-')
            version = sdebVer[0]
            release = '-'.join(sdebVer[1:])
        else:
            version = debVer
            release = ''
        self._curObj.version = version
        self._curObj.release = release
