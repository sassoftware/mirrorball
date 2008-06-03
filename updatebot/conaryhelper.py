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

    def getSourceTroves(self, group=None):
        """
        Find all of the source troves included in group. If group is None use
        the top level group config option.
        @param group: optional argument to specify the group to query
        @type group: None or troveTuple (name, versionStr, flavorStr)
        @return set of source trove specs
        """

        if not group:
            group = self._cfg.topGroup

        trvlst = self._repos.findTrove(self._ccfg.buildLabel, group)

        srcTrvs = set()
        for trv in self._findLatest(trvlst):
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
                                          skipNotByDefault=False)

        topTrove = self._getTrove(cs, name, version, flavor)

        srcTrvs = set()
        for n, v, f in topTrove.iterTroveList(weakRefs=True):
            trv = self._getTrove(cs, n, v, f)
            srcTrvs.add((trv.getSourceName(), v.getSourceVersion(), None))

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

        troveCs = cs.getNewTroveVersion(name, version, flavor)
        trv = trove.Trove(troveCs, skipIntegrityChecks=True)
        return trv


if __name__ == '__main__':
    import sys
    from conary.lib import util as cnyutil
    sys.excepthook = cnyutil.genExcepthook()

    from updatebot import config
    Cfg = config.UpdateBotConfig()
    Cfg.topGroup = ('group-dist', 'sle.rpath.com@rpath:sle-devel', None)
    Cfg.configPath = '../'

    Obj = ConaryHelper(Cfg)
    SrcTrvs = Obj.getSourceTroves()

    import epdb
    epdb.st()
