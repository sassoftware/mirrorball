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

slog = log.addRootLogger()
cfg = UpdateBotConfig()
cfg.read(os.path.join(confDir, 'updatebotrc'))

bot = Bot(cfg)

from updatebot import groupmgr

versionFactory = groupmgr.VersionFactory(cfg)
pkgset = bot._updater.getSourceVersionMap()
sources = set([ (x, y.trailingRevision().getVersion())
                for x, y in pkgset.iteritems() ])

match = versionFactory.getVersions(sources)

import epdb; epdb.st()
