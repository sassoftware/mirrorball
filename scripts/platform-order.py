#!/usr/bin/python
#
# Copyright (c) rPath, Inc.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#


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
