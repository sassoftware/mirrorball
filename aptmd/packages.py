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

from aptmd.common import BaseContainer, BaseParser

class _Package(BaseContainer):
    __slots__ = ('source', 'location', 'summary', 'description')


class PackagesParser(BaseParser):

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

    def _source(self):
        source = self._getLine()
        assert source != ''
        self._curObj.source = source

    def _filename(self):
        self._curObj.location = self._getLine()

    def _description(self):
        self._curObj.summary = self._getLine()

    def _bugs(self):
        self._curObj.description = self._text
        self._keyval()
