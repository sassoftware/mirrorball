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
