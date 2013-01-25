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
