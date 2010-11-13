#!/usr/bin/python
#
# Copyright (c) 2010 rPath, Inc.
#
# This program is distributed under the terms of the Common Public License,
# version 1.0. A copy of this license should have been distributed with this
# source file in a file called LICENSE. If it is not present, the license
# is always available at http://www.rpath.com/permanent/licenses/CPL-1.0.
#
# This program is distributed in the hope that it will be useful, but
# without any warranty; without even the implied warranty of merchantability
# or fitness for a particular purpose. See the Common Public License for
#

"""
Script for promoting groups in the correct order.
"""

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
from updatebot import OrderedBot
from updatebot import UpdateBotConfig

slog = log.addRootLogger()
cfg = UpdateBotConfig()
cfg.read(os.path.join(confDir, 'updatebotrc'))

if cfg.platformName == 'rhel':
    import rhnmirror

    mcfg = rhnmirror.MirrorConfig()
    mcfg.read(confDir + '/erratarc')

    errata = rhnmirror.Errata(mcfg)
    errata.fetch()

    bot = OrderedBot(cfg, errata)

else:
    bot = OrderedBot(cfg, None)

    if cfg.platformName == 'sles':
        from errata.sles import AdvisoryManager as Errata

    elif cfg.platformName == 'sles11':
        from errata.sles11 import AdvisoryManager11 as Errata

    elif cfg.platformName == 'centos':
        from errata.centos import AdvisoryManager as Errata

    else:
        raise RuntimeError, 'no errata source found for %s' % cfg.platformName

    errata = Errata(bot._pkgSource)
    bot._errata._errata = errata

bot.promote(enforceAllExpected=True, checkMissingPackages=True)

import epdb; epdb.st()
