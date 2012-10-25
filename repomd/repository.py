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

        fd, name = tempfile.mkstemp(prefix='mdparse')
        return name

    def _getRealUrl(self, path):
        """
        @param path: relative path to repository file
        @type path: string
        @return full repository url
        """

        return self._repoUrl + '/' + path
