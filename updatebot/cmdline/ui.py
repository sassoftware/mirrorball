#
# Copyright (c) 2010 rPath, Inc.
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
Basic client user interface callback for mirrorball.
"""

from updatebot.lib import util

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


class UserInterface(object):
    """
    Basic user interface class.
    @param cfg: client config object
    @type cfg: updatebot.cmdline.clientcfg.UpdateBotClientConfig
    """

    def __init__(self, cfg):
        self._cfg = cfg

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

        if not self._cfg.interactive:
            return default

        if default is True:
            prompt += ' [Y/n]:'
        elif default is False:
            prompt += ' [y/N]:'

        return util.askYn(prompt, default)
