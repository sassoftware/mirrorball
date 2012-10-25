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
