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
Generate update information based on the ordering of a pkgSource.
"""

import time
import logging

from updatebot.lib import util

from errata import common
from errata.common import Nevra
from errata.common import Package
from errata.common import Channel
from errata.common import Advisory

log = logging.getLogger('errata')

class AdvisoryManager(common.AdvisoryManager):
    def __init__(self, pkgSource):
        common.AdvisoryManager.__init__(self)

        self._pkgSource = pkgSource

        self._channels = {}
        self._advOrder = {}
        self._advisories = set()

    @common.reqfetch
    def iterByIssueDate(self):
        """
        Yields Errata objects by the issue date of the errata.
        """

        for updateId in sorted(self._advOrder):
            for adv in self._advOrder[updateId]:
                yield adv

    def fetch(self):
        """
        Retrieve all required advisory data.

        This is probably going to cache any data, probably in a database, that
        is being fetched from the internet somewhere so that we don't cause
        excesive load for anyone's servers.
        """

        self._order()
        self._fetched = True
        return self._advisories

    @common.reqfetch
    def getChannels(self):
        """
        Get a list of indexed channel names.
        @return list of indexed channel names
        """

        return self._channels.keys()

    def cleanup(self):
        """
        Free all cached results.
        """

        self._channels = {}
        self._advOrder = {}
        self._advisories = set()

    def getModifiedErrata(self, updateId):
        """
        Get a list of any errata that were modified after updateId and were
        issued before updateId.
        """

        return []

    def _order(self):
        """
        Fetch all patch data from the package source.
        """

        def slice(ts):
            """
            Convert a time stamp into the desired time slice.
            """

            # convert to current day
            return int(time.mktime(time.strptime(time.strftime('%Y%m%d',
                        time.gmtime(ts)), '%Y%m%d')))

        def getChannel(pkg):
            for label, channel in self._channels.iteritems():
                if label in pkg.location:
                    return channel

        # make sure the pkg source is loaded.
        self._pkgSource.load()

        # Sort packages by build timestamp.
        slices = {}
        for srcPkg in self._pkgSource.srcPkgMap:
            if int(srcPkg.buildTimestamp) < 1286870401 or not srcPkg.fileTimestamp:
                updateId = slice(int(srcPkg.buildTimestamp))
            else:
                updateId = slice(int(srcPkg.fileTimestamp))
            # If package comes from a base path, override updateId
            for basePath in self._pkgSource._cfg.repositoryBasePaths:
                if basePath[1].match(srcPkg.location) is not None:
                    updateId = 0
                    break
            slices.setdefault(updateId, set()).add(srcPkg)

        # find labels
        for label in self._pkgSource._clients:
            self._channels[label] = Channel(label)

        # make package objects from binaries
        nevras = {}
        packages = {}
        srcPkgMap = {}

        seen = set()
        startedUpdates = False
        for sliceId, srcPkgs in sorted(slices.iteritems()):
            for srcPkg in srcPkgs:
                # Assume everything before we see a dupllicate source name is in
                # the base set of packages.
                if srcPkg.name not in seen and not startedUpdates:
                    seen.add(srcPkg.name)
                    continue
                startedUpdates = True

                pkgSet = srcPkgMap.setdefault(srcPkg, set())
                for binPkg in self._pkgSource.srcPkgMap[srcPkg]:
                    if binPkg.arch == 'src':
                        continue

                    # Get a nevra object
                    nevra = binPkg.getNevra()
                    nevraObj = nevras.setdefault(nevra, Nevra(*nevra))

                    # Get a channel object
                    channelObj = getChannel(binPkg)

                    # Create a package object
                    package = Package(channelObj, nevraObj)
                    packageObj = packages.setdefault(package, package)

                    # Add packages to the package map
                    srcPkgMap.setdefault(srcPkg, set()).add(packageObj)

        # create advisories
        for sliceId, srcPkgs in slices.iteritems():
            for srcPkg in srcPkgs:
                # If this source is not in the srcPkgMap it is probably
                # considered to be in the base set of packages.
                if srcPkg not in srcPkgMap:
                    continue

                # Collect everything needed to make an advisory.
                advisory = 'cu-%s' % srcPkg
                synopsis = 'update of %s' % srcPkg
                issue_date = time.strftime('%Y-%m-%d %H:%M:%S',
                    time.gmtime(sliceId))
                packages = srcPkgMap[srcPkg]

                # Create a fake advisory.
                log.info('creating advisory: %s' % advisory)
                adv = Advisory(advisory, synopsis, issue_date, packages)
                self._advisories.add(adv)
                self._advOrder.setdefault(sliceId, set()).add(adv)
