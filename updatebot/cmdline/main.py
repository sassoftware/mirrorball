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

import sys
import logging

from conary.lib import util
from conary.lib import options

from updatebot import errors
from updatebot import constants
from updatebot import log as logger
from updatebot.cmdline import command
from updatebot.cmdline import clientcfg

class BotMain(options.MainHandler):
    name = 'updatebot'
    version = constants.version

    abstractCommand = command.BotCommand
    configClass = clientcfg.UpdateBotClientConfig

    useConaryOptions = False

    commandList = command._commands

    def usage(self, rc=1, showAll=False):
        if not showAll:
            print ('Common Commands (use "%s help" for the full list)'
                   % self.name)
        return options.MainHandler.usage(self, rc, showAll=showAll)

    def runCommand(self, thisCommand, *args, **kw):
        return options.MainHandler.runCommand(self, thisCommand, *args, **kw)


def main(argv):
    rootLogger = logger.addRootLogger()
    log = logging.getLogger('updatebot.main')
    try:
        argv = list(argv)
        debugAll = '--debug-all' in argv
        debuggerException = errors.UpdateBotError
        if debugAll:
            debuggerException = Exception
            argv.remove('--debug-all')
        sys.excepthook = util.genExcepthook(debug=debugAll,
                                            debugCtrlC=debugAll)
        return BotMain().main(argv, debuggerException=debuggerException)
    except debuggerException, err:
        raise
    except IOError, e:
        # allow broken pipe to exit
        if e.errno != errno.EPIPE:
            raise
    except KeyboardInterrupt:
        return 1
    return 0
