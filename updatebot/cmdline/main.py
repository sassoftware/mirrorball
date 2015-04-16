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
