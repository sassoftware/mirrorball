#!/usr/bin/python

import os
import sys

sys.path.insert(0, os.environ['HOME'] + '/hg/conary')
sys.path.insert(0, os.environ['HOME'] + '/hg/xobj/py')
sys.path.insert(0, os.environ['HOME'] + '/hg/rbuilder-trunk/rpath-xmllib')

from conary.lib import util
sys.excepthook = util.genExcepthook()

mbdir = os.path.abspath('../')
sys.path.insert(0, mbdir)

confDir = os.path.join(mbdir, 'config', 'rhel5test')

from updatebot import log
from updatebot import Bot
from updatebot import UpdateBotConfig

import time
import logging

slog = logging.getLogger('script')

log.addRootLogger()
cfg = UpdateBotConfig()
cfg.read(os.path.join(confDir, 'updatebotrc'))

bot = Bot(cfg)

from updatebot import groupmgr

mgr = groupmgr.GroupManager(cfg)

trvMap = mgr._helper._getLatestTroves()

from conary.deps import deps

troves = mgr._helper._getLatestTroves()
for name, vf in troves.iteritems():
    if ':' in name or bot._updater._fltrPkg(name):
        continue

    assert len(vf.keys()) == 1
    version = vf.keys()[0]
    flavors = vf[version]
    mgr.addPackage(name, version, flavors)

mgr._commit()


import epdb; epdb.st()
