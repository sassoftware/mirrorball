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
Mirrorball plugin interface.
"""

from updatebot import log
from updatebot import build
from updatebot import config

from rbuild import pluginapi

class MirrorBall(pluginapi.Plugin):
    def initialize(self):
        """
        Setup initial state.
        """

        store, product = self.handle.productStore, self.handle.product
        ui = self.handle.ui
        cny = self.handle.facade.conary
        rmk = self.handle.facade.rmake

        # This happens when we aren't in a rBuild checkout directory. Most
        # common case, probably when "rbuild init" is being run. Bail since we
        # can't do anyhthing anyway.
        if not store:
            return

        activeStage = store.getActiveStageName()
        activeLabel = product.getLabelForStage(activeStage)
        #nextStage = store.getNextStageName(activeStage)
        #nextLabel = product.getLabelForStage(nextStage)

        self.conarycfg = cny.getConaryConfig()
        self.rmakecfg, contextNames = rmk._getRmakeConfigWithContexts()
        self.updatebotcfg = config.UpdateBotConfig()

        self.updatebotcfg.archContexts = [
            (x, None) for x in contextNames.itervalues() ]

        self.conarycfg.buildLabel = cny._getLabel(activeLabel)

        self.builder = build.Builder(
            self.updatebotcfg,
            ui,
            conaryCfg=self.conarycfg,
            rmakeCfg=self.rmakecfg
        )

        log.addRootLogger()

    def buildmany(self, packages, lateCommit=False, workers=None, retries=None):
        if not hasattr(self, 'builder'):
            self.handle.ui.writeError('Command run outside of expected '
                'context, make sure you are in a checkout directory')
            return

        pkgs = set([ (x, self.conarycfg.buildLabel.asString(), None)
            for x in packages ])



        return self.builder.buildmany(pkgs, lateCommit=lateCommit,
                workers=workers, retries=retries)
