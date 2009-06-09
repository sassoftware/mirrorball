#
# Copyright (c) 2008-2009 rPath, Inc.
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
Advisory module for SLES.
"""

import logging

from updatebot.advisories.common import BaseAdvisory
from updatebot.advisories.sles import Advisor as BaseAdvisor

log = logging.getLogger('updatebot.advisories')

class SLES11Advisory(BaseAdvisory):
    template = BaseAdvisory.template + """\

References:
%(references)s
"""

    def setReferences(self, refs):
        """
        populate advisory data based on list of urls.
        """

        self._data['references'] = self._indentFormatList(refs)


class Advisor(BaseAdvisor):
    """
    Class for processing SLES advisory information.
    """

    _advisoryClass = SLES11Advisory

    def load(self):
        """
        Parse the required data to generate a mapping of binary package
        object to patch object for a given platform into self._pkgMap.
        """

        for path, client in self._pkgSource.getClients().iteritems():
            log.info('loading patch information %s' % path)
            for patch in client.getUpdateInfo():
                patch.summary = patch.title
                patch.packages = patch.pkglist
                self._loadOne(patch, path)

    def _mkAdvisory(self, patch):
        """
        Create and populate advisory object for a given package.
        """

        advisory = BaseAdvisor._mkAdvisory(self, patch)
        advisory.setReferences([ x.href for x in patch.references])
        return advisory

    def _hasException(self, binPkg):
        """
        Check the config for repositories with exceptions for sending
        advisories. (io. repositories that we generated metadata for.)
        @param binPkg: binary package object
        @type binPkg: repomd.packagexml._Package
        """

        res = BaseAdvisor._hasException(self, binPkg)
        if res:
            return True

        for n in ('-debuginfo', '-debugsource'):
            if n in binPkg.location:
                return True

        return False

    def _checkForDuplicates(self, patchSet):
        """
        Check a set of "patch" objects for duplicates. If there are duplicates
        combine any required information into the first object in the set and
        return True, otherwise return False.
        """

        patchLst = list(patchSet)

        if not len(patchLst):
            return False

        patch = patchLst.pop(0)

        for p in patchLst:
            if patch.title == p.title and patch.description == p.description:
                for pkg in p.pkglist:
                    if pkg not in patch.pkglist:
                        patch.pkglist.append(pkg)

        return True
