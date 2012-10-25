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
Module for parsing Ubuntu mail archives.
"""

from pmap.common import BaseParser
from pmap.common import BaseContainer

class UbuntuContainer(BaseContainer):
    """
    Ubuntu specific container class.
    """

    _slots = ('pkgs', 'pkgNameVersion')

    def finalize(self):
        """
        Finalize the instance.
        """

        # E1101 - Instance has no member
        # pylint: disable-msg=E1101

        # W0201 - Attribute defined outside of __init__
        # pylint: disable-msg=W0201

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
        """
        Create a new container instance.
        """

        if self._curObj and not self._curObj.pkgs:
            self._curObj = None
        BaseParser._newContainer(self)

    def _parseLine(self, cfgline):
        """
        Parse a single line.
        """

        cfgline = cfgline.strip()
        return BaseParser._parseLine(self, cfgline)

    def _getState(self, state):
        """
        Find the correct state.
        """

        state = BaseParser._getState(self, state)
        if state in self._states:
            return state

        if self._curDistroVer is not None:
            return 'pkgnamever'

        return state

    def _headersep(self):
        """
        Parse header serparator.
        """

        if len(self._line) != 1:
            return

        if not self._inHeader and not self._endHeader:
            self._inHeader = True
        else:
            self._endHeader = True
            self._inHeader = False

    def _the(self):
        """
        Parse lines starting in "the".
        """

        if self._endHeader and self._text.strip():
            self._curObj.description = self._text.strip()

    def _ubuntu(self):
        """
        Parse Ubuntu lines.
        """

        if '.' in self._line[1] and len(self._line[1].split('.')) == 2:
            year, month = self._line[1].strip(':').split('.')
            if year.isdigit() and month.isdigit():
                self._curDistroVer = self._line[1].strip(':')

    def _pkgnamever(self):
        """
        Parse the package name and version line.
        """

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
        """
        Parse repository Url line.
        """

        url = self._line[0]
        parts = url.split('/')

        # probaby a repository url
        if parts[3] == 'ubuntu' and parts[4] == 'pool':
            if self._curObj.pkgs is None:
                self._curObj.pkgs = set()
            self._curObj.pkgs.add('/'.join(parts[4:]))

    def _details(self):
        """
        Find the begining of the description section.
        """

        if self._line[1] == 'follow:':
            self._curDistroVer = None
            self._inDetails = True
            self._endHeader = False

    def _updated(self):
        """
        Find the end of the description section.
        """

        if self._line[1] == 'packages':
            self._processDetails()

    def _source(self):
        """
        Find the end of the description section.
        """

        if self._line[1] == 'archives:':
            self._processDetails()

    def _processDetails(self):
        """
        Process the description section.
        """

        if self._inDetails or self._endHeader:
            self._inDetails = False
            if self._curObj.description is None:
                self._curObj.description = self._text.strip()
