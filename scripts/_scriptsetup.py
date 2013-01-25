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

mirrorballDir = os.path.realpath(os.path.dirname(__file__) + '/..')
sys.path.insert(0, mirrorballDir)
sys.path.insert(0, mirrorballDir + '/include')

if 'CONARY_PATH' in os.environ:
    sys.path.insert(0, os.environ['CONARY_PATH'])

import conary
import updatebot

print >>sys.stderr, 'using conary from', os.path.dirname(conary.__file__)
print >>sys.stderr, 'using updatebot from', os.path.dirname(updatebot.__file__)

from conary.lib import util
sys.excepthook = util.genExcepthook()

from updatebot import log as logSetup
logSetup.addRootLogger()

from updatebot import OrderedBot
def getBot(botClass=OrderedBot, *args, **kwargs):
    from updatebot import config
    cfg = config.UpdateBotConfig()
    cfg.read(os.path.join(mirrorballDir, 'config', sys.argv[1], 'updatebotrc'))
    return botClass(cfg, *args, **kwargs)
