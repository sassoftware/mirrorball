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

import re
import logging
log = logging.getLogger('pmap.centos')

from pmap.common import BaseParser
from pmap.common import BaseContainer

class CentOSAdvisory(BaseContainer):
    __slots__ = ('discard', 'archs', 'header', 'pkgs', 'upstreamAdvisoryUrl', )

    def finalize(self):
        BaseContainer.finalize(self)

        assert self.subject is not None
        self.summary = self.subject
        self.description = self.upstreamAdvisoryUrl


class Parser(BaseParser):
    def __init__(self):
        BaseParser.__init__(self)

        self._containerClass = CentOSAdvisory
        self._states.update({
            'rhnurl'            : self._rhnurl,
            'updates'           : self._updates,
            'supportedarch'     : self._supportedarch,
            'unsupportedarch'   : self._unsupportedarch,
            'centos'            : self._header,
            'upstream'          : self._rhnurl,
            'sha1'              : self._sha1,
        })

        self._supportedArchRE = '(noarch|src|i386|i686|x86_64)'
        self._suparch = re.compile(self._supportedArchRE)

        self._filter('^.*rhn\.redhat\.com.*$', 'rhnurl')
        self._filter('^updates.*', 'updates')
        self._filter('^%s' % self._supportedArchRE, 'supportedarch')
        self._filter('(ia64|s390|s390x)', 'unsupportedarch')
        self._filter('^[a-z0-9]{32}$', 'sha1')

    def _newContainer(self):
        if self._curObj and self._curObj.discard:
            self._curObj = None
        BaseParser._newContainer(self)

    def _discard(self, force=False):
        if self._curObj.discard is None:
            log.debug('discarding message: %s' % self._curObj.subject)
            self._curObj.discard = True

    def _addPkg(self, pkg):
        if self._curObj.pkgs is None:
            self._curObj.pkgs = set()
        if not pkg.endswith('.rpm'):
            return
        self._curObj.pkgs.add(pkg)

    def _rhnurl(self):
        line = self._getFullLine()
        self._curObj.upstreamAdvisoryUrl = line[line.find('http'):line.find('html')+4]

    def _updates(self):
        pkg = self._getFullLine().split('/')[-1]
        self._addPkg(pkg)

    def _supportedarch(self):
        self._curObj.discard = False
        if self._curObj.archs is None:
            self._curObj.archs = set()
        self._curObj.archs.add(self._line[0])

    def _unsupportedarch(self):
        self._discard()

    def _header(self):
        if self._line[1] == 'Errata' and self._line[3] == 'Security':
            self._curObj.header = self._getFullLine()

    def _sha1(self):
        self._addPkg(self._line[-1])
