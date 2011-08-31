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
