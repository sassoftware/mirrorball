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
Module for walking url trees much like os.walk
"""

import os
import urllib2
import urlparse
from HTMLParser import HTMLParser

class Parser(HTMLParser):
    """
    Parse hrefs out of html documents.
    """

    def __init__(self, callback):
        HTMLParser.__init__(self)
        self._callback = callback

    def handle_starttag(self, tag, attrs):
        """
        Parse "a" tags.
        """

        if tag == 'a':
            d = dict(attrs)
            if 'href' in d:
                self._callback._regref(d['href'])


class UrlWalker(object):
    """
    Class to implement walker interface for urls, similar to os.walk.
    """

    _ignore = ('/', )

    def __init__(self, baseUrl):
        url = urlparse.urlparse(baseUrl)
        self._baseUrl = url.geturl()[:-len(url.path)]
        self._cur = os.path.abspath(url.path)

        self._prev = None
        self._parser = Parser(self)
        self._refs = []

    @classmethod
    def walk(cls, baseUrl):
        """
        Walk a url path.
        """

        obj = cls(baseUrl)
        return obj._walk()

    def _walk(self, prev=None):
        """
        Walk url path.
        """

        files = []
        directories = []

        for path in self._read():
            if self._isDirectory(path):
                if not self._filterDirectory(path, prev):
                    directories.append(os.path.normpath(path))
            elif not self._filterFile(path):
                files.append(path)

        yield (self._getCurrentUrl(), directories, files)

        cur = self._cur
        for directory in directories:
            self._cur = os.path.normpath(os.path.join(cur, directory))
            for res in self._walk(prev=cur):
                yield res

    def _read(self):
        """
        Read a url path and parse the html.
        """

        self._refs = []
        url = self._getCurrentUrl()
        doc = urllib2.urlopen(url).read()
        self._parser.feed(doc)
        self._parser.close()
        return self._refs

    def _regref(self, ref):
        """
        Callback for the html parser to register hrefs.
        """

        self._refs.append(ref)

    def _getCurrentUrl(self):
        """
        Return the current url.
        """

        if self._cur == '/':
            return self._baseUrl

        base = self._baseUrl.endswith('/')
        cur = self._cur.startswith('/')

        if (base and not cur) or (not base and cur):
            return self._baseUrl + self._cur
        elif not base and not cur:
            return self._baseUrl + '/' + self._cur
        elif base and cur:
            return self._baseUrl + self._cur[1:]

    @staticmethod
    def _isDirectory(name):
        """
        Check if an href is a directory.
        """

        return name.endswith('/')

    def _filterDirectory(self, name, prev):
        """
        Check if a directory should be filtered out.
        """

        name = os.path.normpath(name)

        if prev is None and self._cur.startswith(name):
            return True
        if name == self._cur:
            return True
        if name == prev:
            return True
        if name in self._ignore:
            return True

        return False

    @staticmethod
    def _filterFile(name):
        """
        Check if a file should be filtered out.
        """

        # looks like an apache internal file.
        if name.startswith('?'):
            return True

        return False

walk = UrlWalker.walk

if __name__ == '__main__':
    import sys
    from conary.lib import util as cutil
    sys.excepthook = cutil.genExcepthook()

    for cur, dirs, files in UrlWalker.walk(sys.argv[1]):
        print 'cur :', cur
        for d in dirs:
            print 'dir :', d
        #for f in files:
        #    print 'file:', f
