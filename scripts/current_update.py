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

from _scriptsetup import mirrorballDir

from updatebot import config
from updatebot import current

def usage():
    print 'usage: %s <platform>' % sys.argv[0]
    sys.exit(1)

platform = sys.argv[1]
if platform not in os.listdir(mirrorballDir + '/config'):
    usage()

restoreFile=None
if len(sys.argv) > 2:
    restoreFile = sys.argv[2]

confDir = mirrorballDir + '/config/' + platform

cfg = config.UpdateBotConfig()
cfg.read(confDir + '/updatebotrc')

fltr = None

bot = current.Bot(cfg)
pkgMap = bot.update(fltr=fltr)
#bot.buildgroups()

import epdb; epdb.st()
