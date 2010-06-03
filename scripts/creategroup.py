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

import logging

from updatebot import OrderedBot

log = logging.getLogger('tmplogger')

class Bot(OrderedBot):
    def generateInitialGroup(self):
        """
        Generate config for standard group contents based on repository history.
        """

        self._pkgSource.load()

        log.info('getting latest troves')
        troves = self._updater._conaryhelper._getLatestTroves()

        # combine packages of the same name.
        trvs = {}
        for name, vMap in troves.iteritems():
            if name.endswith(':source'):
                continue
            name = name.split(':')[0]
            for version, flavors in vMap.iteritems():
                for flv in flavors:
                    trvs.setdefault(name, dict()).setdefault(version, set()).add(flv)

        pkgs = set()
        for name, vMap in trvs.iteritems():
            if name.endswith(':source'):
                continue
            name = name.split(':')[0]
            for version, flavors in vMap.iteritems():
                data = (name, version, tuple(flavors))
                pkgs.add(data)

        group = self._groupmgr.getGroup()

        for name, version, flavors in pkgs:
            log.info('adding %s=%s' % (name, version))
            for flv in flavors:
                log.info('\t%s' % flv)
            group.addPackage(name, version, flavors)

        group.errataState = 0
        group.version = 'sp3'

        group._groups.pop('group-standard', None)

        removals = set()
        nevras = dict([ (x.getNevra(), y)
            for x, y in self._pkgSource.srcPkgMap.iteritems() ])

        for updateId in range(0, group.errataState + 1):
            self._modifyGroups(updateId, group)

            for srcNevra in self._cfg.removeSource.get(updateId, ()):
                removals.update(set([ x.name for x in nevras[srcNevra] ]))

            removals |= set(self._cfg.updateRemovesPackages.get(updateId, ()))

        for name in removals:
            group.removePackage(name, missingOk=True)

        group._copyVersions()
        group._sanityCheck()
        group._mgr._persistGroup(group)

        import epdb; epdb.st()

        group.commit()
        built = group.build()

        import epdb; epdb.st()

        return built

if __name__ == '__main__':
    from updatebot import config
    from updatebot import log as logSetup

    logSetup.addRootLogger()

    log = logging.getLogger('create group')

    cfg = config.UpdateBotConfig()
    cfg.read(mirrorballDir + '/config/%s/updatebotrc' % sys.argv[1])

    bot = Bot(cfg, None)
    bot._pkgSource.load()
    changes = bot.generateInitialGroup()

    import epdb; epdb.st()
