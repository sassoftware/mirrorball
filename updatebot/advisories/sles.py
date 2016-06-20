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
