#!/usr/bin/python
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

import os
import sys
import traceback

if __name__ == '__main__':
    mirrorballDir = os.path.abspath('../')
    sys.path.insert(0, mirrorballDir)

    if 'CONARY_PATH' in os.environ:
        sys.path.insert(0, os.environ['CONARY_PATH'])

    import rmake
    import conary
    import updatebot

    print >>sys.stderr, 'using conary from', os.path.dirname(conary.__file__)
    print >>sys.stderr, 'using rmake from', os.path.dirname(rmake.__file__)
    print >>sys.stderr, 'using updatebot from', os.path.dirname(updatebot.__file__)

    from conary.lib import util
    sys.excepthook = util.genExcepthook()

    from updatebot import log as logSetup
    logSetup.addRootLogger()

import logging

from updatebot import OrderedBot

log = logging.getLogger('create group')

class Bot(OrderedBot):
    def mapGroup(self, currentLabel, targetLabel):
        """
        Generate config for standard group contents based on repository history.
        """

        # Get the latest group model.
        self._pkgSource.load()
        group = self._groupmgr.getGroup()

        # oldLabel = the label that should *not* be referenced
        # clonedFromInfo = dict([ (k, v) for (k, v) in self._updater._conaryhelper.getClonedFromForLabel(conary.versions.Label(currentLabel)).iteritems() ])
        clonedFromInfo = dict([ (k, v) for (k, v) in self._updater._conaryhelper.getClonedFromForLabel(conary.versions.Label(targetLabel)).iteritems() ])
        packagelist = [ x for x in group.iterpackages() if (not x.version.startswith('/' + targetLabel) and
                        x.version.startswith('/' + currentLabel)) ]
        newpackagelist = [ clonedFromInfo[(p0.name, conary.versions.ThawVersion(p0.version), conary.deps.deps.ThawFlavor(str(p0.flavor)))] for p0 in packagelist ]

        assert len(newpackagelist) == len([x for x in newpackagelist if x[1].asString().startswith('/' + targetLabel) ])
        # for RHEL5C add: or x[1].asString().startswith('/rhel.rpath.com@rpath:rhel-5-server-devel') ])
        newtrovelist = self._updater._conaryhelper.findTroves(newpackagelist)
        for val in newtrovelist.values():
            assert len(val) == 1
        newpackagelist = [ x[0] for x in newtrovelist.values() ]

        pkgs = {}
        for n, v, f in newpackagelist:
            pkgs.setdefault(n, dict()).setdefault(v, set()).add(f)
        for n, vMap in pkgs.iteritems():
            assert len(vMap) == 1
            group.removePackage(n)
            for v, flvs in vMap.iteritems():
                group.addPackage(n, v, flvs)

        import epdb; epdb.st()
        group._readOnly = False
        try:
            group = group.commit()
        except AssertionError:
            print traceback.format_exc(sys.exc_info()[2])

        return group 

if __name__ == '__main__':
    from updatebot import config

    cfg = config.UpdateBotConfig()
    cfg.read(mirrorballDir + '/config/%s/updatebotrc' % sys.argv[1])

    bot = Bot(cfg, None)
    model = bot.mapGroup(sys.argv[2], sys.argv[3])

    import epdb; epdb.st()
