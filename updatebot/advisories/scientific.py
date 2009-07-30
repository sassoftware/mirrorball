#
# Copyright (c) 2009 rPath, Inc.
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
Advisory module for Scientific Linux.
"""

from updatebot.advisories.centos import Advisor as BaseAdvisor

class Advisor(BaseAdvisor):
    def _loadOne(self, msg, pkgCache):
        """
        Handles matching one message to any mentioned packages.
        """

        # Filter out messages that don't have a summary or description.
        if msg.summary is None or msg.description is None:
            return

        BaseAdvisor._loadOne(self, msg, pkgCache)

    def _isUpdatesRepo(self, binPkg):
        """
        Check the repository name. If this package didn't come from a updates
        repository it is probably not security related.
        @param binPkg: binary package object
        @type binPkg: repomd.packagexml._Package
        """

        parts = binPkg.location.split('/')
        if parts[2] == 'updates' and not parts[3] == 'fastbugs':
            return True
        return False
