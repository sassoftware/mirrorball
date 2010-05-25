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
            updateId = slice(int(srcPkg.buildTimestamp))
            slices.setdefault(updateId, set()).set(srcPkg)

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
