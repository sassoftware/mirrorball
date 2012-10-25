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
PMAP - PiperMail Archive Parser

Parse advisories from pipermail archives.
"""

import os
import gzip
import shutil
import urllib2
import tempfile

from imputil import imp

__all__ = ('InvalidBackendError', 'ArchiveNotFoundError', 'parse')
__supportedBackends = ('ubuntu', 'centos', 'scientific')

class InvalidBackendError(Exception):
    """
    Raised when requested backend is not available.
    """

class ArchiveNotFoundError(Exception):
    """
    Raised when an archive could not be retrieved.
    """

def _getFileObjFromUrl(url):
    """
    Given a URL download the file, gunzip if needed, and return an open
    file object.
    """

    fn = tempfile.mktemp(prefix='pmap')

    # download file
    try:
        inf = urllib2.urlopen(url)
    except urllib2.HTTPError, e:
        if e.getcode() == 404:
            raise ArchiveNotFoundError, e
    outf = open(fn, 'w')
    shutil.copyfileobj(inf, outf)

    if url.endswith('.gz'):
        fh = gzip.open(fn)
    else:
        fh = open(fn)

    os.unlink(fn)
    return fh

def _getBackend(backend):
    """
    If the requested backend exists find it and return the backend module,
    otherwise raise an exception.
    """

    if backend not in __supportedBackends:
        raise InvalidBackendError('%s is not a supported backend, please '
            'choose from %s' % (backend, ','.join(__supportedBackends)))

    try:
        path = [imp.find_module('pmap')[1], ]
        mod = imp.find_module(backend, path)
        loaded = imp.load_module(backend, mod[0], mod[1], mod[2])
        return loaded
    except ImportError, e:
        raise InvalidBackendError('Could not load %s backend: %s'
                                  % (backend, e))

def parse(url, **kwargs):
    """
    Parse a mbox archive pointed to by url.
    """

    backend = kwargs.pop('backend')

    fh = _getFileObjFromUrl(url)
    backend = _getBackend(backend)
    parser = backend.Parser(**kwargs)
    return parser.parse(fh)
