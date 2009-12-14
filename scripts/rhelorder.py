#!/usr/bin/python

import os
import sys
import tempfile

sys.path.insert(0, os.environ['HOME'] + '/hg/conary')
sys.path.insert(0, os.environ['HOME'] + '/hg/rhnmirror')
sys.path.insert(0, os.environ['HOME'] + '/hg/rbuilder-5.5/rpath-xmllib')
sys.path.insert(0, os.environ['HOME'] + '/hg/rbuilder-5.5/rpath-capsule-indexer')

from conary.lib import util
sys.excepthook = util.genExcepthook()

mbdir = os.path.abspath('../')
sys.path.insert(0, mbdir)

confDir = os.path.join(mbdir, 'config', 'rhel5')

from updatebot import log
from updatebot.ordered import Bot
from updatebot import UpdateBotConfig

import rhnmirror

slog = log.addRootLogger()

mcfg = rhnmirror.MirrorConfig()
mcfg.read(confDir + '/erratarc')
#mcfg.indexerDb += '5'
#mcfg.indexerDb = 'sqlite:///%s' % tempfile.mktemp(suffix='.db', prefix='order-')

slog.info('db = %s' % mcfg.indexerDb)

#mcfg.channels = [
#    'rhel-x86_64-server-5',
#    'rhel-i386-server-5',
#    'rhel-x86_64-as-4',
#    'rhel-i386-as-4',
#]

errata = rhnmirror.Errata(mcfg)
errata.fetch()

cfg = UpdateBotConfig()
cfg.read(os.path.join(confDir, 'updatebotrc'))

bot = Bot(cfg, errata)
bot._pkgSource.load()
bot._errata._orderErrata()

import epdb; epdb.st()
