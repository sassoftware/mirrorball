#
# Copyright (c) 2008-2009 rPath, Inc.
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
