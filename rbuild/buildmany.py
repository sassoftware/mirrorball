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

"""
rBuild plugin to bring buildmany support to rBuild users.
"""

from rbuild import errors
from rbuild import pluginapi
from rbuild.pluginapi import command

class BuildManyCommand(command.BaseCommand):
    help = 'Build many packages in sepparate rmake jobs'
    commands = ['buildmany', ]
    paramHelp = '[package]*'
    docs = {
        'late-commit': 'wait until all builds are done before committing',
        'workers': 'number of active jobs (default 30)'
    }

    def addLocalParameters(self, argDef):
        argDef['late-commit'] = command.NO_PARAM
        argDef['workers'] = command.ONE_PARAM

    def runCommand(self, handle, argSet, args):
        lateCommit = argSet.pop('late-commit', False)
        workers = int(argSet.pop('workers', 30))
        _, pkgList = self.requireParameters(args, allowExtra=True)
        results = handle.MirrorBall.buildmany(pkgList, lateCommit=lateCommit,
                workers=workers)

        if not results:
            raise errors.PluginError('pacakges failed to build')


class BuildMany(pluginapi.Plugin):
    def registerCommands(self):
        self.handle.Commands.registerCommand(BuildManyCommand)
