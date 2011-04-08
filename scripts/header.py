#
# Copyright (c) 2008-2009 rPath, Inc.
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

import os
import sys
import tempfile

from _scriptsetup import mirrorballDir

from conary.lib import util
sys.excepthook = util.genExcepthook()

from updatebot import build
from updatebot import config

def usage():
    print 'usage: %s <platform> [pkg1, pkg2, ...]' % sys.argv[0]
    sys.exit(1)

if len(sys.argv) < 2 or sys.argv[1] not in os.listdir(mirrorballDir + '/config'):
    usage()

cfg = config.UpdateBotConfig()
cfg.read(mirrorballDir + '/config/%s/updatebotrc' % sys.argv[1])

from updatebot.cmdline import UserInterface

ui = UserInterface()

builder = build.Builder(cfg, ui)

def displayTrove(nvf):
    flavor = ''
    if nvf[2] is not None:
        flavor = '[%s]' % nvf[2]

    return '%s=%s%s' % (nvf[0], nvf[1], flavor)

def display(trvMap):
    for srcTrv in sorted(trvMap.iterkeys()):
        print displayTrove(srcTrv)
        for binTrv in sorted(trvMap[srcTrv]):
            print " " * 4, displayTrove(binTrv)
