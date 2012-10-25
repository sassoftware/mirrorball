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
Module for walking url trees much like os.walk
"""

import os
import urllib2
import urlparse
from HTMLParser import HTMLParser

from updatebot.lib import util

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
