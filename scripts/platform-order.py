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

slog = log.addRootLogger()

cfg = UpdateBotConfig()
cfg.read(os.path.join(confDir, 'updatebotrc'))

if cfg.platformName == 'rhel':
    import rhnmirror

    mcfg = rhnmirror.MirrorConfig()
    mcfg.read(confDir + '/erratarc')

    errata = rhnmirror.Errata(mcfg)
    bot = Bot(cfg, errata)
    
else:
    bot = Bot(cfg, None)

    if cfg.platformName == 'sles':
        from errata.sles import AdvisoryManager as Errata
    elif cfg.platformName == 'sles11':
        from errata.sles11 import AdvisoryManager11 as Errata
    elif cfg.platformName == 'centos':
        from errata.centos import AdvisoryManager as Errata
    else:
        raise RuntimeError, 'unsupported platformName'

    errata = Errata(bot._pkgSource)
    bot._errata._errata = errata

errata.fetch()

bot._pkgSource.load()
bot._errata._orderErrata()

# For easy inspection.
order = bot._errata._order

def tconv(tstamp):
    return time.strftime('%m-%d-%Y %H:%M:%S', time.localtime(tstamp))

childPackages, parentPackages = bot._errata.sanityCheckOrder()

if cfg.platformName != 'rhel':
    missingPackages, missingOrder = bot._checkMissingPackages()

import epdb; epdb.st()