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
Module for common utility functions.
"""

# W0611 - Unused import rmtree
# pylint: disable-msg=W0611

import os
import epdb
import signal
import resource

from rmake.lib import osutil
from conary.lib.util import rmtree
from conary.lib.util import convertPackageNameToClassName as _pkgNameToClassName

from rpmutils import rpmvercmp

def join(a, *b):
    """
    Version of os.path.join that doesn't reroot when it finds a leading /.
    """

    root = os.path.normpath(a)
    if root == '/':
        root = ''
    for path in b:
        root += os.sep + os.path.normpath(path)
    return os.path.abspath(root)

def srpmToConaryVersion(srcPkg):
    """
    Get the equvialent conary version from a srcPkg object.
    @param srcPkg: package object for a srpm
    @type srcPkg: repomd.packagexml._Package
    @return conary trailing version
    """

    version = srcPkg.version.replace('-', '_')
    release = srcPkg.release.replace('-', '_')
    cnyver = '_'.join([version, release])
    return cnyver

def packagevercmp(a, b):
    """
    Compare two package objects.
    @param a: package object from repo metadata
    @type a: repomd.packagexml._Package
    @param b: package object from repo metadata
    @type b: repomd.packagexml._Package
    """

    # Not all "packages" have epoch set. If comparing between two packages, at
    # least one without an epoch specified, ignore epoch.
    if a.epoch is not None and b.epoch is not None:
        epochcmp = rpmvercmp(a.epoch, b.epoch)
        if epochcmp != 0:
            return epochcmp

    vercmp = rpmvercmp(a.version, b.version)
    if vercmp != 0:
        return vercmp

    relcmp = rpmvercmp(a.release, b.release)
    if relcmp != 0:
        return relcmp

    return 0

def packageCompare(a, b):
    """
    Compare package with arch.
    """

    pkgvercmp = packagevercmp(a, b)
    if pkgvercmp != 0:
        return pkgvercmp

    archcmp = cmp(a.arch, b.arch)
    if archcmp != 0:
        return archcmp

    return 0

def packageCompareByName(a, b):
    """
    Compare packages by name and the follow packagevercmp.
    """

    nameCmp = cmp(a.name, b.name)
    if nameCmp != 0:
        return nameCmp

    return packagevercmp(a, b)

class Metadata(object):
    """
    Base class for repository metadata.
    """

    def __init__(self, pkgs):
        self.pkgs = pkgs
        self.locationMap = {}
        self.binPkgMap = {}

        src = None
        for pkg in self.pkgs:
            if hasattr(pkg, 'location'):
                self.locationMap[pkg.location] = pkg
            elif hasattr(pkg, 'files'):
                for path in pkg.files:
                    self.locationMap[path] = pkg
            if pkg.arch == 'src':
                src = pkg

        for pkg in self.pkgs:
            self.binPkgMap[pkg] = src

def isKernelModulePackage(paths):
    """
    Check if a package file name or location is a kernel module.
    """

    if type(paths) == str:
        paths = [ paths, ]

    for path in paths:
        basePath = os.path.basename(path)
        if (basePath.startswith('kmod-') or
            basePath.startswith('kernel-module') or
            '-kmod' in basePath):
            return True
    return False

def setMaxRLimit():
    """
    Set the max file descriptors to the maximum allowed.
    """

    cur, max = resource.getrlimit(resource.RLIMIT_NOFILE)
    resource.setrlimit(resource.RLIMIT_NOFILE, (max, max))
    return max

def getRLimit():
    """
    Get the current number of file descriptors.
    """

    cur, max = resource.getrlimit(resource.RLIMIT_NOFILE)
    return cur

def getAvailableFileDescriptors(setMax=False):
    """
    Get the number of available file descriptors.
    """

    openfds = len(os.listdir('/proc/self/fd'))
    if setMax:
        setMaxRLimit()
    limit = getRLimit()
    return limit - openfds

def setupDebugHandler(serve=False):
    """
    Sets up a USR1 signal handler to trigger epdb.serv().
    """

    def handler(signum, sigtb):
        if serve:
            epdb.serve()
        else:
            epdb.st()

    signal.signal(signal.SIGUSR1, handler)

def convertPackageNameToClassName(pkgName):
    name = _pkgNameToClassName(pkgName)
    return name.replace('.', '_')

def askYn(prompt, default=None):
    while True:
        try:
            resp = raw_input(prompt + ' ')
        except EOFError:
            return False

        resp = resp.lower()
        if resp in ('y', 'yes'):
            return True
        elif resp in ('n', 'no'):
            return False
        elif resp in ('d', 'debug'):
            epdb.st()
        elif not resp:
            return default
        else:
            print "Unknown response '%s'." % resp

def setproctitle(title):
    try:
        osutil.setproctitle('mirrorball %s' % (title,))
    except:
        pass

class BoundedCounter(object):
    """
    Basic counter that can be incremented and decremented while enforcing
    bounds.
    """

    def __init__(self, low, high, cur, boundsErrors=True):
        self._low = low
        self._high = high
        self._cur = cur
        self._boundsErrors = boundsErrors

    def __str__(self):
        return str(self._cur)

    def __repr__(self):
        return '<Counter(%s, %s, %s)>' % (self._low, self._high, self._cur)

    def __bool__(self):
        if self._cur == self._low:
            return False
        else:
            return True

    def __len__(self):
        return self._cur - self._low

    def __add__(self, other):
        if isinstance(other, int):
            while other:
                self.increment()
                other -= 1
        else:
            raise RuntimeError, 'Counters only support adding integers'

        return self

    def __sub__(self, other):
        if isinstance(other, int):
            while other:
                self.decrement()
                other -= 1
        else:
            raise RuntimeError, 'Counters only support subtracting integers'

        return self

    def __cmp__(self, other):
        if isinstance(other, int):
            return cmp(self._cur, other)
        elif isinstance(other, self.__class__):
            return cmp(self._cur, other._cur)
        else:
            raise (RuntimeError, 'Counters only support comparision operations '
                   'against integers and other Counter instances')

    @property
    def upperlimit(self):
        return self._high

    @property
    def lowerlimit(self):
        return self._low

    def increment(self):
        if self._cur + 1 <= self._high:
            self._cur += 1
        elif self._boundsErrors:
            raise RuntimeError, 'Counter has been incremented past upper bounds'

    def decrement(self):
        if self._cur - 1 >= self._low:
            self._cur -= 1
        elif self._boundsErrors:
            raise RuntimeError, 'Counter has been decremented past lower bounds'
