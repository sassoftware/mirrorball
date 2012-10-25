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
Top level advisories module.
"""

import logging
from imputil import imp

log = logging.getLogger('updatebot.advisories')

_supportedBackends = ('sles', 'sles11', 'centos', 'ubuntu', 'scientific', )

class InvalidBackendError(Exception):
    """
    Raised when an unsupported backend is used.
    """


class _UnsupportedAdivsor(object):
    """
    Stub object to raise exception on access rather than instantiation.
    """

    class Advisor(object):
        def __init__(self, cfg, backend):
            self.backend = backend

        def __getattr__(self, name):
            if name == 'backend':
                return getattr(self, name)
            raise InvalidBackendError('%s is not a supported backend, please '
                'choose from %s' % (self.backend, ','.join(_supportedBackends)))


def __getBackend(backend):
    if backend not in _supportedBackends:
        return _UnsupportedAdivsor

    try:
        updatebotPath = [imp.find_module('updatebot')[1], ]
        advisoriesPath = [imp.find_module('advisories', updatebotPath)[1], ]
        mod = imp.find_module(backend, advisoriesPath)
        loaded = imp.load_module(backend, mod[0], mod[1], mod[2])
        return loaded
    except ImportError, e:
        raise InvalidBackendError('Could not load %s backend: %s'
                                  % (backend, e))

def Advisor(cfg, pkgSource, backend):
    """
    Get an instance of an advisor for a given backend.
    """

    module = __getBackend(backend)
    obj = module.Advisor(cfg, pkgSource)
    return obj
