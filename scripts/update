#!/usr/bin/python

import os
import sys

sys.path.insert(0, os.environ['HOME'] + '/hg/rpath-xmllib')
sys.path.insert(0, os.environ['HOME'] + '/hg/conary')
sys.path.insert(0, os.environ['HOME'] + '/hg/mirrorball')
sys.path.insert(0, os.environ['HOME'] + '/hg/rmake')
sys.path.insert(0, os.environ['HOME'] + '/hg/xobj/py')

from updatebot import log
log.addRootLogger()

from conary.lib import util
sys.excepthook = util.genExcepthook()

from updatebot import bot, config

cfg = config.UpdateBotConfig()
cfg.read(os.environ['HOME'] + '/hg/mirrorball/config/ubuntu/updatebotrc')
obj = bot.Bot(cfg)
obj.update()
