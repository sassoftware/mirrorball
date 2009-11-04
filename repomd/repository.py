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
Repository access module.
"""

__all__ = ('Repository', )

import os
import gzip
import shutil
import tempfile
import urllib2

class Repository(object):
    """
    Access files from the repository.
    """

    def __init__(self, repoUrl):
        self._repoUrl = repoUrl

    def get(self, fileName):
        """
        Download a file from the repository.
        @param fileName: relative path to file
        @type fileName: string
        @return open file instance
        """

        fn = self._getTempFile()
        realUrl = self._getRealUrl(fileName)

        inf = urllib2.urlopen(realUrl)
        outf = open(fn, 'w')
        shutil.copyfileobj(inf, outf)

        if os.path.basename(fileName).endswith('.gz'):
            fh = gzip.open(fn)
        else:
            fh = open(fn)
        os.unlink(fn)
        return fh

    @classmethod
    def _getTempFile(cls):
        """
        Generate a tempory filename.
        @return name of tempory file
        """

        return tempfile.mktemp(prefix='mdparse')

    def _getRealUrl(self, path):
        """
        @param path: relative path to repository file
        @type path: string
        @return full repository url
        """

        return self._repoUrl + '/' + path
