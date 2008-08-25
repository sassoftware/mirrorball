#!/usr/bin/python

import sys
from conary.lib import util
sys.excepthook = util.genExcepthook()

import logging
import updatebot.log

updatebot.log.addRootLogger()
log = logging.getLogger('test')

from aptmd import Client
from updatebot import config
from updatebot import pkgsource

cfg = config.UpdateBotConfig()
cfg.read('/data/hg/mirrorball/config/ubuntu/updatebotrc')

client = Client('http://i.rdu.rpath.com/ubuntu')
pkgSource = pkgsource.PackageSource(cfg)

for path in cfg.repositoryPaths:
    log.info('loading %s' % path)
    pkgSource.loadFromClient(client, path)

pkgSource.finalize()

import epdb; epdb.st()
