#!/usr/bin/python
#
# Copyright (c) rPath, Inc.
#
# This program is distributed under the terms of the Common Public License,
# version 1.0. A copy of this license should have been distributed with this
# source file in a file called LICENSE. If it is not present, the license
# is always available at http://www.rpath.com/permanent/licenses/CPL-1.0.
#
# This program is distributed in the hope that it will be useful, but
# without any warranty; without even the implied warranty of merchantability
# or fitness for a particular purpose. See the Common Public License for
# full details.
#

from _scriptsetup import getBot, mirrorballDir

import os
import sys
import logging

from updatebot import config
from updatebot import ordered

log = logging.getLogger('script')

def usage():
    print 'usage: %s <platform>' % sys.argv[0]
    sys.exit(1)

platform = sys.argv[1]
if platform not in os.listdir(mirrorballDir + '/config'):
    usage()

confDir = mirrorballDir + '/config/' + platform

cfg = config.UpdateBotConfig()
cfg.read(confDir + '/updatebotrc')

fltr = None

if cfg.platformName == 'rhel':
    import rhnmirror

    mcfg = rhnmirror.MirrorConfig()
    mcfg.read(confDir + '/erratarc')

    errata = rhnmirror.Errata(mcfg)
    errata.fetch()

    bot = ordered.Bot(cfg, errata)

else:
    bot = ordered.Bot(cfg, None)

    if cfg.platformName == 'sles':
        from errata.sles import AdvisoryManager as Errata

    elif cfg.platformName == 'centos':
        from errata.centos import AdvisoryManager as Errata

    elif cfg.platformName in ('sles11', 'sles11sp1hae'):
        from errata.sles11 import AdvisoryManager11 as Errata

    else:
        raise RuntimeError, 'no errata source found for %s' % cfg.platformName

    errata = Errata(bot._pkgSource)
    bot._errata._errata = errata


pkgMap, failures = bot.create(fltr=fltr)

