#!/usr/bin/python

import os
import sys
import time
import tempfile

sys.path.insert(0, os.environ['HOME'] + '/hg/conary')
sys.path.insert(0, os.environ['HOME'] + '/hg/rhnmirror')
sys.path.insert(0, os.environ['HOME'] + '/hg/rbuilder-5.5/rpath-xmllib')
sys.path.insert(0, os.environ['HOME'] + '/hg/rbuilder-5.5/rpath-capsule-indexer')

from conary.lib import util
sys.excepthook = util.genExcepthook()

mbdir = os.path.abspath('../')
sys.path.insert(0, mbdir)

confDir = os.path.join(mbdir, 'config', sys.argv[1])

from updatebot import log
from updatebot import cmdline
from updatebot import pkgsource
from updatebot import UpdateBotConfig
from updatebot.ordered import Bot

from errata.sles import AdvisoryManager as Errata

slog = log.addRootLogger()

cfg = UpdateBotConfig()
cfg.read(os.path.join(confDir, 'updatebotrc'))

ui = cmdline.UserInterface()

pkgSource = pkgsource.PackageSource(cfg, ui)

errata = Errata(pkgSource)
errata.fetch()

bot = Bot(cfg, errata)
bot._pkgSource.load()
bot._errata._orderErrata()

order = bot._errata._order
advMap = bot._errata._advMap
sorder = sorted(order)

def tconv(tstamp):
    return time.strftime('%m-%d-%Y %H:%M:%S', time.localtime(tstamp))

childPackages, parentPackages = bot._errata.sanityCheckOrder()

import epdb; epdb.st()
