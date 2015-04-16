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


class BuildPackageCommand(BotCommand):
    """
    Build a list of packages.
    """

    commands = [ 'buildpackages', ]
    help = 'build packages'

    def runCommand(self, client, cfg, argSet, args):
        pass
