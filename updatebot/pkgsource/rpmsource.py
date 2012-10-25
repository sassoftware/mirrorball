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
Module for interacting with a directory of packages.
"""

import os
import logging

from conary import rpmhelper

log = logging.getLogger('updatebot.pkgsource')

from repomd.packagexml import _Package
from rpmutils import header as rpmheader

from updatebot.lib import urlwalker
from updatebot.pkgsource.yumsource import YumSource as PackageSource

class Package(_Package):
    """
    Class for represnting package data.
    """

    def __init__(self, *args, **kwargs):
        _Package.__init__(self, *args)
        for key, val in kwargs.iteritems():
            setattr(self, key, val)

    def getNevra(self):
        """
        Return the name, epoch, version, release, and arch the package.
        """

        return (self.name, self.epoch, self.version, self.release, self.arch)

    def getConaryVersion(self):
        """
        Get the conary version of a source package.
        """

        assert self.arch == 'src'
        filename = os.path.basename(self.location)
        nameVerRelease = ".".join(filename.split(".")[:-2])
        ver = "_".join(nameVerRelease.split("-")[-2:])
        return ver


class Client(object):
    """
    Client class for walking package tree.
    """

    walkMethod = os.walk

    def __init__(self, path):
        self._path = path

    def getPackageDetail(self):
        """
        Walk the specified path to find rpms.
        """

        idx = 0
        for path, dirs, files in self.walkMethod(self._path):
            for f in files:
                if f.endswith('.rpm'):
                    idx += 1
                    if idx % 50 == 0:
                        log.info('indexing %s' % idx)
                    yield self._index(os.path.join(path, f))

    def _index(self, rpm):
        """
        Index an individual rpm.
        """

        fh = rpmheader.SeekableStream(rpm)
        h = rpmhelper.readHeader(fh)
        name = h[rpmhelper.NAME]
        epoch = h.get(rpmhelper.EPOCH, None)
        if isinstance(epoch, (list, tuple)):
            assert len(epoch) == 1
            epoch = str(epoch[0])
        version = h[rpmhelper.VERSION]
        release = h[rpmhelper.RELEASE]
        arch = h.isSource and 'src' or h[rpmhelper.ARCH]
        sourcename = h.get(rpmhelper.SOURCERPM, None)

        basename = os.path.basename(rpm)
        pkg = Package(name=name,
                      epoch=epoch,
                      version=version,
                      release=release,
                      arch=arch,
                      sourcerpm=sourcename,
                      location=basename)
        return pkg


class UrlClient(Client):
    """
    Url based client.
    """

    walkMethod = urlwalker.walk


class RpmSource(PackageSource):
    PkgClass = Package

    def iterPackageSet(self):
        """
        Iterate over the set of source packages.
        """

        for srcPkg, binPkgs in self.srcPkgMap.iteritems():
            if not len(binPkgs):
                continue
            yield (srcPkg.name, srcPkg.getConaryVersion())

    def _excludeLocation(self, location):
        # FIXME: This should not be hard coded. There needs to be a config
        #        option for exclusions.
        path = os.path.dirname(location)
        if 'VT' in path or 'Cluster' in path:
            return True

class _RpmSource(PackageSource):
    """
    Walk a directory, find rpms, index them.
    """

    PkgClass = Package

    def __init__(self, cfg, ui, path=None):
        PackageSource.__init__(self, cfg, ui)
        self._path = path

    def load(self):
        """
        load package source.
        """

        if self._loaded:
            return

        if not self.path:
            return

        log.info('loading %s' % self._path)

        client = Client(self._path)
        self.loadFromClient(client)

        self.finalize()
        self._loaded = True

    def loadFromUrl(self, url, basePath=''):
        """
        This method is not supported for indexing, raise a decent error.
        """

        if self._loaded:
            return

        fullUrl = url + '/' + basePath

        log.info('loading %s' % fullUrl)

        client = UrlClient(fullUrl)
        self.loadFromClient(client, basePath=basePath)

        self.finalize()
        self._loaded = True

    def iterPackageSet(self):
        """
        Iterate over the set of source packages.
        """

        for srcPkg, binPkgs in self.srcPkgMap.iteritems():
            if not len(binPkgs):
                continue
            yield (srcPkg.name, srcPkg.getConaryVersion())
