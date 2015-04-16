#!/usr/bin/python
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
