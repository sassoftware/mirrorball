#!/usr/bin/python

import os
import sys
import time

from _scriptsetup import mirrorballDir as mbdir

confDir = os.path.join(mbdir, 'config', sys.argv[1])

from updatebot.ordered import Bot
from updatebot import UpdateBotConfig


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
    elif cfg.platformName in ('sles11', 'sles11sp1hae'):
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
