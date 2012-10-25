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

from updatebot.advisories.common import BaseAdvisor

log = logging.getLogger('updatebot.advisories')

class Advisor(BaseAdvisor):
    """
    Class for processing SLES advisory information.
    """

    allowExtraPackages = True

    def load(self):
        """
        Parse the required data to generate a mapping of binary package
        object to patch object for a given platform into self._pkgMap.
        """

        for path, client in self._pkgSource.getClients().iteritems():
            log.info('loading patch information %s' % path)
            for patch in client.getPatchDetail():
                self._loadOne(patch, path)

    def _loadOne(self, patch, path):
        """
        Load one patch into mappings.
        @param patch: repomd patch object
        @type patch: repomd.patchxml._Patch
        @param path: base path to repository
        @type path: string
        """

        if self._filterPatch(patch):
            return

        for package in patch.packages:
            package.location = path + '/' + package.location
            if package not in self._pkgMap:
                self._pkgMap[package] = set()
            self._pkgMap[package].add(patch)

    def _hasException(self, binPkg):
        """
        Check the config for repositories with exceptions for sending
        advisories. (io. repositories that we generated metadata for.)
        @param binPkg: binary package object
        @type binPkg: repomd.packagexml._Package
        """

        shortPath = binPkg.location.split('/')[0]

        for advisoryException in self._cfg.advisoryException:
            path = advisoryException[0].split('/')[0]
            if path == shortPath:
                return True
        return False

    def _isUpdatesRepo(self, binPkg):
        """
        Check the repository name. If this package didn't come from a updates
        repository it is probably not security related.
        @param binPkg: binary package object
        @type binPkg: repomd.packagexml._Package
        """

        # msw agrees that this seems to be a sane check.

        shortPath = binPkg.location.split('/')[0]

        if shortPath.endswith('Updates'):
            return True
        else:
            return False

    def _checkForDuplicates(self, patchSet):
        """
        Check a set of "patch" objects for duplicates. If there are duplicates
        combine any required information into the first object in the set and
        return True, otherwise return False.
        """

        # W0613 - Unused argument patchSet
        # pylint: disable-msg=W0613
        
        # Don't have dups on sles 
        # Now we do have duplicates in sles
        # Testing code from centos

        if not len(patchSet):
            return False

        primary = list(patchSet)[0]

        for patch in patchSet:
            if patch is primary:
                continue
            if primary.name != patch.name:
                return False

            log.warn('''Duplicate detected in %s and %s''' % 
                     (primary.name, patch.name))

            # Copy pkg data into the primary
            # FIXME: This is not the correct solution need more than rpm list
            # Need to add the descriptions and patch numbers when updating
            # Possible add an update method 

            primary.packages.append(patch.packages)

        return True
