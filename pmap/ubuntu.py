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
Module for parsing Ubuntu mail archives.
"""

from pmap.common import BaseParser
from pmap.common import BaseContainer

class UbuntuContainer(BaseContainer):
    """
    Ubuntu specific container class.
    """

    __slots__ = ('pkgs', 'pkgNameVersion')

    def finalize(self):
        BaseContainer.finalize(self)

        assert self.subject is not None
        assert self.pkgs is not None
        assert self.description is not None
        assert self.pkgNameVersion is not None

        self.summary = self.subject

class Parser(BaseParser):
    """
    Class for parsing Ubuntu mbox mail archives.
    """

    def __init__(self):
        BaseParser.__init__(self)

        self._containerClass = UbuntuContainer

        self._curDistroVer = None
        self._inDetails = False
        self._inHeader = False
        self._endHeader = False

        self._states.update({
            'headersep'         : self._headersep,
            'setdescription'    : self._the,
            'ubuntu'            : self._ubuntu,
            'pkgnamever'        : self._pkgnamever,
            'repourl'           : self._repourl,
            'details'           : self._details,
            'updated'           : self._updated,
            'source'            : self._source,
        })

        self._filter('^.*security\.ubuntu\.com/ubuntu.*$', 'repourl')
        self._filterLine('^=*$', 'headersep')
        self._filterLine('^The problem can be corrected.*$', 'setdescription')

    def _newContainer(self):
        if self._curObj and not self._curObj.pkgs:
            self._curObj = None
        BaseParser._newContainer(self)

    def _parseLine(self, cfgline):
        cfgline = cfgline.strip()
        return BaseParser._parseLine(self, cfgline)

    def _getState(self, state):
        state = BaseParser._getState(self, state)
        if state in self._states:
            return state

        if self._curDistroVer is not None:
            return 'pkgnamever'

        return state

    def _headersep(self):
        if len(self._line) != 1:
            return

        if not self._inHeader and not self._endHeader:
            self._inHeader = True
        else:
            self._endHeader = True
            self._inHeader = False

    def _the(self):
        if self._endHeader and self._text.strip():
            self._curObj.description = self._text.strip()

    def _ubuntu(self):
        if '.' in self._line[1] and len(self._line[1].split('.')) == 2:
            year, month = self._line[1].strip(':').split('.')
            if year.isdigit() and month.isdigit():
                self._curDistroVer = self._line[1].strip(':')

    def _pkgnamever(self):
        # looks like a version
        line = [ x for x in self._line if x ]

        if len(line) == 2:
            name, version = line
            if self._curObj.pkgNameVersion is None:
                self._curObj.pkgNameVersion = {}

            if self._curDistroVer not in self._curObj.pkgNameVersion:
                self._curObj.pkgNameVersion[self._curDistroVer] = set()

            self._curObj.pkgNameVersion[self._curDistroVer].add((name, version))

    def _repourl(self):
        url = self._line[0]
        parts = url.split('/')

        # probaby a repository url
        if parts[3] == 'ubuntu' and parts[4] == 'pool':
            if self._curObj.pkgs is None:
                self._curObj.pkgs = set()
            self._curObj.pkgs.add('/'.join(parts[4:]))

    def _details(self):
        if self._line[1] == 'follow:':
            self._curDistroVer = None
            self._inDetails = True
            self._endHeader = False

    def _updated(self):
        if self._line[1] == 'packages':
            self._processDetails()

    def _source(self):
        if self._line[1] == 'archives:':
            self._processDetails()

    def _processDetails(self):
        if self._inDetails or self._endHeader:
            self._inDetails = False
            if self._curObj.description is None:
                self._curObj.description = self._text.strip()
