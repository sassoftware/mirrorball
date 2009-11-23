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

confDir = os.path.join(mbdir, 'config', sys.argv[1])

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

troves = mgr._helper._getLatestTroves()
mgr._checkout()

import epdb; epdb.st()

for name, vf in troves.iteritems():
    if ':' in name or bot._updater._fltrPkg(name):
        continue

    versions = vf.keys()
    versions.sort()
    version = versions[-1]
    flavors = vf[version]
#    mgr.addPackage(name, version, flavors)

mgr.setVersion('0')
mgr.setErrataState('0')
mgr._commit()
#mgr.build()

import epdb; epdb.st()
