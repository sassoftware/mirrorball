#
# Copyright (c) 2008 rPath, Inc.
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
