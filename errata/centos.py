#
# Copyright (c) 2010 rPath, Inc.
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

        def srtByNevra(a, b):
            return util.packagevercmp(a, b)

        def srtByBuildTime(a, b):
            assert hasattr(a, 'buildTimestamp')
            assert hasattr(b, 'buildTimestamp')
            assert a.buildTimestamp not in ('0', '', 0)
            assert b.buildTimestamp not in ('0', '', 0)
            return cmp(int(a.buildTimestamp), int(b.buildTimestamp))

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

        # Make sure that nevra order and build time order are the same for each
        # source name.
        order = {}
        for srcName, srcPkgs in self._pkgSource.srcNameMap.iteritems():
            log.info('checking %s' % srcName)
            sortedNevras = sorted(srcPkgs, cmp=srtByNevra)
            sortedBuildTime = sorted(srcPkgs, cmp=srtByBuildTime)
            assert sortedNevras == sortedBuildTime

            for srcPkg in srcPkgs:
                assert srcPkg.buildTimestamp is not None
                order.setdefault(int(srcPkg.buildTimestamp), set()).add(srcPkg)

        slices = {}
        for updateId, srcPkgs in order.iteritems():
            slices.setdefault(slice(updateId), set()).update(srcPkgs)

        # find labels
        for label in self._pkgSource._clients:
            self._channels[label] = Channel(label)

        # make package objects from binaries
        nevras = {}
        packages = {}
        srcPkgMap = {}
        for sliceId, srcPkgs in slices.iteritems():
            for srcPkg in srcPkgs:
                pkgSet = srcPkgMap.setdefault(srcPkg, set())
                for binPkg in self._pkgSource.srcPkgMap[srcPkg]:
                    if binPkg.arch == 'src':
                        continue
                    nevra = binPkg.getNevra()
                    nevraObj = nevras.setdefault(nevra, Nevra(*nevra))
                    channelObj = getChannel(binPkg)
                    package = Package(channelObj, nevraObj)
                    packageObj = packages.setdefault(package, package)
                    srcPkgMap.setdefault(srcPkg, set()).add(packageObj)

        # create advisories
        for sliceId, srcPkgs in slices.iteritems():
            for srcPkg in srcPkgs:
                advisory = 'cu-%s' % srcPkg
                synopsis = 'update of %s' % srcPkg
                issue_date = time.strftime('%Y-%m-%d %H:%M:%S',
                    time.gmtime(sliceId))
                packages = srcPkgMap[srcPkg]

                adv = Advisory(advisory, synopsis, issue_date, packages)
                self._advisories.add(adv)
                self._advOrder.setdefault(sliceId, set()).add(adv)

                log.info('creating advisory: %s' % advisory)
