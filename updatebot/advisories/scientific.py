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
