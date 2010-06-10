#!/usr/bin/python
#
# Copyright (c) 2009 rPath, Inc.
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

import sys
from conary.lib import util

sys.excepthook = util.genExcepthook()

import os

sys.path.insert(0, os.environ['HOME'] + '/hg/mirrorball')

from updatebot import config
from updatebot import pkgsource
from updatebot import log as logger
from updatebot import cmdline

logger.addRootLogger()

cfg = config.UpdateBotConfig()
cfg.read(os.environ['HOME'] + '/hg/mirrorball/config/scientific/updatebotrc')

ui = cmdline.UserInterface()

pkgSource = pkgsource.PackageSource(cfg, ui)

pkgSource.load()
