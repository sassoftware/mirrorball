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
PMAP - PiperMail Archive Parser

Parse advisories from pipermail archives.
"""

import os
import gzip
import shutil
import urllib2
import tempfile

from imputil import imp

__all__ = ('InvalidBackendError', 'parse')
_supported_backends = ('ubuntu', 'centos')

class InvalidBackendError(Exception):
    """
    Raised when requested backend is not available.
    """

def _getFileObjFromUrl(url):
    """
    Given a URL download the file, gunzip if needed, and return an open
    file object.
    """

    fn = tempfile.mktemp(prefix='pmap')

    # download file
    inf = urllib2.urlopen(url)
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

    if backend not in _supported_backends:
        raise InvalidBackendError('%s is not a supported backend, please '
            'choose from %s' % (backend, ','.join(_supported_backends)))

    try:
        path = [imp.find_module('pmap')[1], ]
        mod = imp.find_module(backend, path)
        loaded = imp.load_module(backend, mod[0], mod[1], mod[2])
        return loaded
    except ImportError, e:
        raise InvalidBackendError('Could not load %s backend: %s'
                                  % (backend, e))

def parse(url, backend='centos'):
    """
    Parse a mbox archive pointed to by url.
    """

    fh = _getFileObjFromUrl(url)
    backend = _getBackend(backend)
    parser = backend.Parser()
    return parser.parse(fh)
