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


"""
Script for promoting groups in the correct order.
"""

from _scriptsetup import mirrorballDir as mbdir
import os
import sys

confDir = os.path.join(mbdir, 'config', sys.argv[1])

from updatebot import OrderedBot
from updatebot import UpdateBotConfig

cfg = UpdateBotConfig()
cfg.read(os.path.join(confDir, 'updatebotrc'))

if cfg.platformName == 'rhel':
    import rhnmirror

    mcfg = rhnmirror.MirrorConfig()
    mcfg.read(confDir + '/erratarc')

    errata = rhnmirror.Errata(mcfg)
    errata.fetch()

    bot = OrderedBot(cfg, errata)

    checkMissingPackages = False

else:
    bot = OrderedBot(cfg, None)

    if cfg.platformName == 'sles':
        from errata.sles import AdvisoryManager as Errata

    elif cfg.platformName in ('sles11', 'sles11sp1hae'):
        from errata.sles11 import AdvisoryManager11 as Errata

    elif cfg.platformName == 'centos':
        from errata.centos import AdvisoryManager as Errata

    else:
        raise RuntimeError, 'no errata source found for %s' % cfg.platformName

    errata = Errata(bot._pkgSource)
    bot._errata._errata = errata

    checkMissingPackages = True

bot.promote(enforceAllExpected=True, checkMissingPackages=checkMissingPackages)

import epdb; epdb.st()
