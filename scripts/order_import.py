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

import epdb; epdb.st()
