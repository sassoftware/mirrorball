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
Module to wrap around conary api. Maybe this could be replaced by rbuild at
some point.
"""

import logging

from conary.deps import deps
from conary import conaryclient, conarycfg, trove

from updatebot import util

log = logging.getLogger('updatebot.conaryhelper')

class ConaryHelper(object):
    """
    Wrapper object for conary api.
    """

    def __init__(self, cfg):
        self._cfg = cfg

        self._ccfg = conarycfg.ConaryConfiguration(readConfigFiles=False)
        self._ccfg.read(util.join(self._cfg.configPath, 'conaryrc'))
        self._ccfg.flavor = deps.parseFlavor('')
        # FIXME: do we need to initialize flavors or not?
        #self._ccfg.initializeFlavors()

        self._client = conaryclient.ConaryClient(self._ccfg)
        self._repos = self._client.getRepos()

    def getConaryConfig(self):
        """
        Get a conary config instance.
        @return conary configuration object
        """

        return self._ccfg

    def getSourceTroves(self, group):
        """
        Find all of the source troves included in group. If group is None use
        the top level group config option.
        @param group: group to query
        @type group: None or troveTuple (name, versionStr, flavorStr)
        @return set of source trove specs
        """

        trvlst = self._repos.findTrove(self._ccfg.buildLabel, group)

        latest = self._findLatest(trvlst)

        # Magic number should probably be a config option.
        # 2 here is the number of flavors expected.
        if len(latest) != 2:
            raise TooManyFlavorsFoundError(why=latest)

        srcTrvs = set()
        for trv in latest:
            log.info('querying %s for source troves' % (trv, ))
            srcTrvs.update(self._getSourceTroves(trv))

        return srcTrvs

    @classmethod
    def _findLatest(cls, trvlst):
        """
        Given a list of trove specs, find the most recent versions.
        @param trvlst: list of trove specs
        @type trvlst: [(name, versionObj, flavorObj), ...]
        @return [(name, versionObj, flavorObj), ...]
        """

        latest = []

        trvlst.sort()
        trvlst.reverse()
        while len(trvlst) > 0:
            trv = trvlst.pop(0)
            if len(latest) == 0 or latest[-1][1] == trv[1]:
                latest.append(trv)
            else:
                break

        return latest

    def _getSourceTroves(self, troveSpec):
        """
        Iterate over the contents of a trv to find all of source troves
        refrenced by that trove.
        @param troveSpec: trove to walk.
        @type troveSpec: (name, versionObj, flavorObj)
        @return set([(trvSpec, trvSpec, ...])
        """

        name, version, flavor = troveSpec
        cl = [ (name, (None, None), (version, flavor), True) ]
        cs = self._client.createChangeSet(cl, withFiles=False,
                                          withFileContents=False,
                                          recurse=False)

        topTrove = self._getTrove(cs, name, version, flavor)

        srcTrvs = set()
        sources = self._repos.getTroveInfo(trove._TROVEINFO_TAG_SOURCENAME,
                        list(topTrove.iterTroveList(weakRefs=True)))
        for i, (n, v, f) in enumerate(topTrove.iterTroveList(weakRefs=True)):
            srcTrvs.add((sources[i](), v.getSourceVersion(), None))

        return srcTrvs

    @classmethod
    def _getTrove(cls, cs, name, version, flavor):
        """
        Get a trove object for a given name, version, flavor from a changeset.
        @param cs: conary changeset object
        @type cs: changeset
        @param name: name of a trove
        @type name: string
        @param version: conary version object
        @type version: conary.versions.Version
        @param flavor: conary flavor object
        @type flavor: conary.deps.Flavor
        @return conary.trove.Trove object
        """

        #log.debug('getting trove for (%s, %s, %s)' % (name, version, flavor))
        troveCs = cs.getNewTroveVersion(name, version, flavor)
        trv = trove.Trove(troveCs, skipIntegrityChecks=True)
        return trv
