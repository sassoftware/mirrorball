#!/usr/bin/python
#
# Copyright (c) 2008 rPath, Inc.
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

sys.path.insert(0, os.environ['HOME'] + '/hg/rpath-xmllib')
sys.path.insert(0, os.environ['HOME'] + '/hg/conary')
sys.path.insert(0, os.environ['HOME'] + '/hg/mirrorball')

from conary.lib import util
sys.excepthook = util.genExcepthook()

from updatebot import bot, config, log

log.addRootLogger()
cfg = config.UpdateBotConfig()
cfg.read(os.environ['HOME'] + '/hg/mirrorball/config/opensuse/updatebotrc')
obj = bot.Bot(cfg)
trvMap = obj.create()

import epdb ; epdb.st()

for source in trvMap:
    for bin in trvMap[source]:
        print '%s=%s[%s]' % bin
