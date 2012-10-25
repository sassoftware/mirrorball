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

if __name__ == '__main__':
    mirrorballDir = os.path.abspath('../')
    sys.path.insert(0, mirrorballDir)

    if 'CONARY_PATH' in os.environ:
        sys.path.insert(0, os.environ['CONARY_PATH'])

    import rmake
    import conary
    import updatebot

    print >>sys.stderr, 'using conary from', os.path.dirname(conary.__file__)
    print >>sys.stderr, 'using rmake from', os.path.dirname(rmake.__file__)
    print >>sys.stderr, 'using updatebot from', os.path.dirname(updatebot.__file__)

    from conary.lib import util
    sys.excepthook = util.genExcepthook()

    from updatebot import log as logSetup
    logSetup.addRootLogger()

import logging

from updatebot import OrderedBot

log = logging.getLogger('scripts.testgroup')

class Bot(OrderedBot):
    def generateInitialGroup(self):
        """
        Generate config for standard group contents based on repository history.
        """

#        self._pkgSource.load()

        # Get the latest group model.
        group = self._groupmgr.getGroup()

#        import epdb; epdb.st()

        trvMap = group.buildmany()

        import epdb; epdb.st()

        # Sanity check the group model and write out the current state so that
        # you can do a local test cook.
        group._copyVersions()
        group._sanityCheck()
        group._setGroupFlags()
        group._mgr._persistGroup(group)

        # You probably want to do a test cook if your groups here. It would be
        # nice if mirrorball could just do this for you, but it can't right now.
        # To run a test cook take a look at group._mgr._helper._checkoutCache to
        # find the directory where the checkout is and then run cvc cook from
        # that directory.
        import epdb; epdb.st()

        # Commit and build the group.
        group = group.commit()
        built = group.build()

        import epdb; epdb.st()

        return built

if __name__ == '__main__':
    from updatebot import config

    cfg = config.UpdateBotConfig()
    cfg.read(mirrorballDir + '/config/%s/updatebotrc' % sys.argv[1])

    bot = Bot(cfg, None)
    trvMap = bot.generateInitialGroup()

    import epdb; epdb.st()
