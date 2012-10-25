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
