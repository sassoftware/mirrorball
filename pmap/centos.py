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
Module for parsing centos mail archives.
"""

import re
import logging
log = logging.getLogger('pmap.centos')

from pmap.common import BaseParser
from pmap.common import BaseContainer

class CentOSAdvisory(BaseContainer):
    """
    Container class for CentOS advisories.
    """

    _slots = ('discard', 'archs', 'header', 'pkgs', 'upstreamAdvisoryUrl', )

    def finalize(self):
        """
        Derive some infomration used for advisories.
        """

        # E1101: Instance of 'CentOSAdvisory' has no 'upstreamAdvisoryUrl'
        #        member
        # W0201: Attribute 'description' defined outside __init__
        # W0201: Attribute 'summary' defined outside __init__
        # pylint: disable-msg=E1101
        # pylint: disable-msg=W0201

        BaseContainer.finalize(self)

        assert self.subject is not None
        self.summary = self.subject
        self.description = self.upstreamAdvisoryUrl


class Parser(BaseParser):
    """
    Parse for CentOS mail archives.
    """

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
        """
        Discard the current container if the discard flag is set.
        """

        if self._curObj and self._curObj.discard:
            self._curObj = None
        BaseParser._newContainer(self)

    def _discard(self, force=False):
        """
        Set the current object to be discarded.
        """

        if self._curObj.discard is None or force:
            log.debug('discarding message: %s' % self._curObj.subject)
            self._curObj.discard = True

    def _addPkg(self, pkg):
        """
        Add package to container.
        """

        if self._curObj.pkgs is None:
            self._curObj.pkgs = set()
        if not pkg.endswith('.rpm'):
            return
        self._curObj.pkgs.add(pkg)

    def _rhnurl(self):
        """
        Set the rhn url.
        """

        line = self._getFullLine()
        self._curObj.upstreamAdvisoryUrl = \
            line[line.find('http'):line.find('html')+4]

    def _updates(self):
        """
        Parse updates.
        """

        pkg = self._getFullLine().split('/')[-1]
        self._addPkg(pkg)

    def _supportedarch(self):
        """
        Filter on supported architectures.
        """

        self._curObj.discard = False
        if self._curObj.archs is None:
            self._curObj.archs = set()
        self._curObj.archs.add(self._line[0])

    def _unsupportedarch(self):
        """
        Discard messages that contain unsupported arches.
        """

        self._discard()

    def _header(self):
        """
        Parse the header.
        """

        if self._line[1] == 'Errata' and self._line[3] == 'Security':
            self._curObj.header = self._getFullLine()

    def _sha1(self):
        """
        Parse sha1 lines.
        """

        self._addPkg(self._line[-1])
