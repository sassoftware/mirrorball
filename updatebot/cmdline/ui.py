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
Basic client user interface callback for mirrorball.
"""

from updatebot.lib import util
from updatebot.cmdline import clientcfg

class AbstractUserInterface(object):
    """
    Abstract class to define user interface interface.
    """

    def ask(self, prompt, default=None):
        """
        Simple method for asking yes/no questions.
        @param prompt: string to prompt the user with.
        @type prompt: str
        @param default: Default value if no input is provided. This value will
                        be used if not running in interactive mode.
        @type default: boolean
        @return boolean value of the answer.
        @rtype boolean
        """

        raise NotImplementedError


class UserInterface(AbstractUserInterface):
    """
    Basic user interface class.
    @param cfg: client config object
    @type cfg: updatebot.cmdline.clientcfg.UpdateBotClientConfig
    """

    def __init__(self, cfg=None):
        if cfg is None:
            self.cfg = clientcfg.UpdateBotClientConfig()
        else:
            self.cfg = cfg

    def ask(self, prompt, default=None):
        """
        Simple method for asking yes/no questions.
        @param prompt: string to prompt the user with.
        @type prompt: str
        @param default: Default value if no input is provided. This value will
                        be used if not running in interactive mode.
        @type default: boolean
        @return boolean value of the answer.
        @rtype boolean
        """

        if not self.cfg.interactive:
            return default

        if default is True:
            prompt += ' [Y/n]:'
        elif default is False:
            prompt += ' [y/N]:'

        return util.askYn(prompt, default)
