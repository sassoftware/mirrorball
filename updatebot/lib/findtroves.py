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
This is a caching implentation of the findTroves call from conary netclient.
"""

import logging

log = logging.getLogger('updatebot.lib.findtroves')

class FindTrovesCache(dict):
    """
    Caching layer for findTroves
    """

    def __init__(self, repos):
        dict.__init__(self)

        self._repos = repos

    def findTroves(self, labelPath, troves, getLeaves=True, cache=True,
        allowMissing=False):
        """
        Emulate the behavior of repos.findTroves while caching results.
        """

        if not cache:
            return self._repos.findTroves(labelPath, troves,
                getLeaves=getLeaves, allowMissing=allowMissing)

        found = set()
        needed = {}

        if not isinstance(labelPath, (list, tuple, set)):
            tlp = (labelPath, )
        else:
            tlp = tuple(labelPath)

        # Separate out items that have already been cached from those that have
        # not.
        for trove in troves:
            key = (tlp, tuple(trove), getLeaves)

            if key in self:
                found.add(key)
            else:
                needed[trove] = key

        # Ask the repo for anything that hasn't been cached.
        if needed:
            if found:
                log.info('CACHE hit on %s troves' % len(found))
            log.info('CACHE querying repository for %s troves' % len(needed))
            results = self._repos.findTroves(labelPath, needed,
                getLeaves=getLeaves, allowMissing=allowMissing)
        else:
            log.info('CACHE hit on all troves')
            results = {}

        # Cache the results.
        for req, res in results.iteritems():
            self[needed[req]] = res

        # Build actual result
        results.update(dict((x[1], self[x]) for x in found))

        return results
