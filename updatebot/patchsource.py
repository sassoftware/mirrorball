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
Module for building datastructures for packages to patches.
"""

import logging

log = logging.getLogger('updatebot.patchsource')

class PatchSource(object):
    """
    Store patch related mappings.
    """

    def __init__(self, cfg):
        self._cfg = cfg

        # {binPkg: patchObj}
        self.pkgMap = dict()

    def loadFromClient(self, client, path):
        """
        Load patch information from a repomd client object.
        @param client: repomd client object
        @type client: repomd.Client
        @param path: base path to repository
        @type path: string
        """

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
            if package not in self.pkgMap:
                self.pkgMap[package] = set()
            self.pkgMap[package].add(patch)

    def _filterPatch(self, patch):
        """
        Filter out patches that match filters in config.
        @param patch: repomd patch object
        @type patch: repomd.patchxml._Patch
        """

        for _, regex in self._cfg.patchFilter:
            if regex.match(patch.summary):
                return True
            if regex.match(patch.description):
                return True

        return False
