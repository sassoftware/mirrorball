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
Command line client configuration.
"""

import os

from conary.lib import cfg
from conary.lib.cfgtypes import CfgBool

from updatebot.config import UpdateBotConfig


class UpdateBotClientConfigSection(cfg.ConfigSection):
    """
    Config class for an updatebot command line client.
    """

    # control to interupt operations based on various conditions
    interactive     = (CfgBool, True)


class UpdateBotClientConfig(UpdateBotConfig):
    """
    Client config object.
    """

    _defaultSectionType = UpdateBotClientConfigSection

    def __init__(self, readConfigFiles=False, ignoreErrors=False):
        UpdateBotConfig.__init__(self)
        self._ignoreErrors = ignoreErrors

        if readConfigFiles:
            self.readFiles()

    def readFiles(self):
        self.read('/etc/updatebot/clientrc', exception=False)
        if 'HOME' in os.environ:
            self.read(os.path.join(os.environ['HOME'], '.updatebot-clientrc'),
                      exception=False)
        self.read('updatebot-clientrc', exception=False)
