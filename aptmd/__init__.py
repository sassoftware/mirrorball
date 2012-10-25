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
Module for pasring Apt repository metadata. Also includes a handy FSM for
parsing text files in general.
"""

import os

from repomd.repository import Repository

from aptmd.sources import SourcesParser
from aptmd.packages import PackagesParser
from aptmd.errors import UnsupportedFileError

class Client(object):
    """
    Class for interacting with apt repositories.
    """

    def __init__(self, repoUrl):
        self._repoUrl = repoUrl

        self._repo = Repository(self._repoUrl)
        self._packages = PackagesParser()
        self._sources = SourcesParser()

    def parse(self, path):
        """
        Parse repository metadata.
        """

        fh = self._repo.get(path)
        basename = os.path.basename(path)
        if basename.startswith('Packages'):
            return self._packages.parse(fh, path)
        elif basename.startswith('Sources'):
            return self._sources.parse(fh, path)
        else:
            raise UnsupportedFileError(path)
