#
# Copyright (c) SAS Institute, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
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
