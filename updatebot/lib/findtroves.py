#
# Copyright (c) SAS Institute, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
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
