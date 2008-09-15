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

from conary.lib import options

from conary.lib.options import NO_PARAM
from conary.lib.options import ONE_PARAM
from conary.lib.options import OPT_PARAM
from conary.lib.options import MULT_PARAM
from conary.lib.options import NORMAL_HELP
from conary.lib.options import VERBOSE_HELP

_commands = []
def register(cmd):
    global _commands
    _commands.append(cmd)


class BotCommand(options.AbstractCommand):
    defaultGroup = 'Common Options'

    docs = {'config'             : (VERBOSE_HELP,
                                    "Set config KEY to VALUE", "'KEY VALUE'"),
            'config-file'        : (VERBOSE_HELP,
                                    "Read PATH config file", "PATH"),
            'context'            : (VERBOSE_HELP,
                                    "Set the configuration context to use"),
            'conary-config-file'  : (VERBOSE_HELP,
                                    "Read PATH conary config file", "PATH"),
            'rmake-config-file'  : (VERBOSE_HELP,
                                    "Read PATH config file", "PATH"),
            'skip-default-config': (VERBOSE_HELP,
                                    "Don't read default configs"),
            'verbose'            : (VERBOSE_HELP,
                                    "Display more detailed information where available") }

    def addParameters(self, argDef):
        d = {}
        d["config"] = MULT_PARAM
        d["config-file"] = MULT_PARAM
        d["context"] = ONE_PARAM
        d["conary-config-file"] = MULT_PARAM
        d["rmake-config-file"] = MULT_PARAM
        d["skip-default-config"] = NO_PARAM
        d["verbose"] = NO_PARAM
        argDef[self.defaultGroup] = d

    def processConfigOptions(self, cfg, cfgMap, argSet):
        pass
