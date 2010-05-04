#
# Copyright (c) 2010 rPath, Inc.
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
Generate update information based on the patch detail in SuSE repositories.
"""

import logging

from errata import common

log = logging.getLogger('errata')

class Package(common.Package):
    """
    Class to represent a package.
    """

    def getNevra(self):
        """
        Returns a tuple of (name, epoch, version, release, arch) for
        this package.
        """

class Repository(common.Repository):
    """
    Class to represent a repository.
    """


class Advisory(common.Advisory):
    """
    Class to represent an errata or advisory.
    """


class AdvisoryManager(common.AdvisoryManager):
    def __init__(self, pkgSource):
        self._pkgSource = pkgSource

        slef._fetched = False
        self._patches = set()

    @common.reqfetch
    def getRepositories(self):
        """
        Returns a list of repository labels that have been fetched.
        """

    @common.reqfetch
    def iterByIssueDate(self):
        """
        Yields Errata objects by the issue date of the errata.
        """

        return []

    def fetch(self):
        """
        Retrieve all required advisory data.

        This is probably going to cache any data, probably in a database, that
        is being fetched from the internet somewhere so that we don't cause
        excesive load for anyone's servers.
        """

        self._fetched = True

    def _fetchPatches(self):
        """
        Fetch all patch data from the package source.
        """

        # make sure the pkg source is loaded.
        self._pkgSource.load()

        # now get the patch data
        patches = set()
        for path, client in self._pkgSource.getClients().iteritems():
            log.info('loading patches for %s' % path)
            patches.update(set(client.getPatchDetail()))

        return patches
