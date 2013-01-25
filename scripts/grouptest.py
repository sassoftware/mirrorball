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
