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
