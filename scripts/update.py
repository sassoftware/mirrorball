#!/usr/bin/python

import os
import sys

sys.path.insert(0, os.environ['HOME'] + '/hg/rpath-xmllib')
sys.path.insert(0, os.environ['HOME'] + '/hg/conary')
sys.path.insert(0, os.environ['HOME'] + '/hg/mirrorball')

from conary.lib import util
sys.excepthook = util.genExcepthook()

from updatebot import bot, config, log

log.addRootLogger()
cfg = config.UpdateBotConfig()
cfg.read(os.environ['HOME'] + '/hg/mirrorball/config/sles/updatebotrc')
obj = bot.Bot(cfg)
obj.update()

import epdb ; epdb.st()
