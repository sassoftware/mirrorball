#!/usr/bin/python2.6

import os
import sys

sys.path.insert(0, os.environ['HOME'] + '/hg/26/rpath-xmllib')
sys.path.insert(0, os.environ['HOME'] + '/hg/26/conary')
sys.path.insert(0, os.environ['HOME'] + '/hg/26/mirrorball')
sys.path.insert(0, os.environ['HOME'] + '/hg/26/rmake')
sys.path.insert(0, os.environ['HOME'] + '/hg/26/epdb')
sys.path.insert(0, os.environ['HOME'] + '/hg/26/xobj/py')

from updatebot import log
log.addRootLogger()

from conary.lib import util
sys.excepthook = util.genExcepthook()

from updatebot import bot, config

cfg = config.UpdateBotConfig()
cfg.read(os.environ['HOME'] + '/hg/26/mirrorball/config/ubuntu/updatebotrc')
obj = bot.Bot(cfg)
obj.update()
