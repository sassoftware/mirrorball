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
