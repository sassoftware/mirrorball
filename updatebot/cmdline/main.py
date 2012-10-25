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
