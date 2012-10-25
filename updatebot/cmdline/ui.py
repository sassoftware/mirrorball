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
