#!/usr/bin/python

import os
import sys
import time

sys.path.insert(0, os.environ['HOME'] + '/hg/conary')

from conary.lib import util
sys.excepthook = util.genExcepthook()

mbdir = os.path.abspath('../')
sys.path.insert(0, mbdir)

confDir = os.path.join(mbdir, 'config', sys.argv[1])

from updatebot import log
from updatebot.ordered import Bot
from updatebot import UpdateBotConfig

from errata.sles11 import AdvisoryManager11 as Errata

slog = log.addRootLogger()

cfg = UpdateBotConfig()
cfg.read(os.path.join(confDir, 'updatebotrc'))

bot = Bot(cfg, None)
errata = Errata(bot._pkgSource)
bot._errata._errata = errata

errata.fetch()

bot._pkgSource.load()
bot._errata._orderErrata()

order = bot._errata._order
advMap = bot._errata._advMap
sorder = sorted(order)

def tconv(tstamp):
    return time.strftime('%m-%d-%Y %H:%M:%S', time.localtime(tstamp))

childPackages, parentPackages = bot._errata.sanityCheckOrder()

import epdb; epdb.st()
