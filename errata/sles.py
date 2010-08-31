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
Generate update information based on the patch detail in SuSE repositories.
"""

import time
import logging

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

        # FIXME: this work here? (cribbed from centos.py)
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

        def bin_timestamp(ts):
            """
            Convert a time stamp into the desired time slice.
            """

            # convert to current day
            return int(time.mktime(time.strptime(time.strftime('%Y%m%d',
                        time.gmtime(ts)), '%Y%m%d')))

        def slice(patches):
            """
            Build a dictionary of binned (sliced) timestamps and patches.
            """

            slices = {}

            for patch in patches:
                # Bin by day:
                updateId = bin_timestamp(int(patch.timestamp))
                # ...or uncomment the below line to disable binning:
                #updateId = int(patch.timestamp)
                slices.setdefault(updateId,
                                  set()).add(patch.getAttribute('patchid'))
            return slices

        def patchidNoRepo(patchid):
            """
            Trims the leading (repository) information from a patchid.
            Used for folding patches across repositories, among other things.
            """
            return '-'.join(patchid.split('-')[1:])

        def map_patchids(slices):
            """
            Build a dictionary of (partial) patchids and their
            corresponding timestamps.  Used to determine if a patchid
            across multiple repositories also has multiple timestamps.
            """

            patchidMap = {}

            for timestamp, patchids in slices.iteritems():
                for patchid in patchids:
                    # Map excludes leading segment of patchid, which
                    # carries repository information; we're folding
                    # across repositories.
                    patchidMap.setdefault(patchidNoRepo(patchid),
                                          set()).add(timestamp)
            return patchidMap

        def getChannel(pkg):
            for label, channel in self._channels.iteritems():
                if label in pkg.location:
                    return channel
            raise RuntimeError , 'unable to find channel for %s' % pkg.location

        def getSrcPkg(binPkg):
            for srcPkg, binPkgs in self._pkgSource.srcPkgMap.iteritems():
                if binPkg in binPkgs:
                    return srcPkg
            raise RuntimeError , 'unable to find source package for %s' % binPkg.location

        def getPatchById(patches, patchid):
            for patch in patches:
                if patch.getAttribute('patchid') == patchid:
                    return patch
            raise RuntimeError , 'unable to find patch %s' % patchid

        # make sure the pkg source is loaded.
        self._pkgSource.load()

        # Each client value is a SLES release/update repository object.
        # self._pkgSource._clients.values()[...]

        # now get the patch data...
        patches = set()

        for path, client in self._pkgSource.getClients().iteritems():
            log.info('loading patches for path %s' % path)
            for patch in client.getPatchDetail():
                for pkg in patch.packages:
                    pkg.location = path + '/' + pkg.location
                patches.add(patch)

        for label in self._pkgSource._clients:
            self._channels[label] = Channel(label)

        # ...and (time-)slice it up.
        slices = slice(patches)

        for timeslice, patchSet in slices.iteritems():
            for patchId in patchSet:
                patchObj = getPatchById(patches, patchId)
                if patchObj.timestamp != timeslice:
                    log.info('syncing %s timestamp (%s) to slice timestamp %s' % (
                    patchId, patchObj.timestamp, timeslice))
                    patchObj.timestamp = timeslice

        # slices dict is still current since the above only synced the
        # patch timestamps to existing slices.

        # This maps patchid (without regard to repos) to timeslices.
        patchidMap = map_patchids(slices)

        # This requires no more than two timestamps per patchid;
        # one each for slesp3 and sdkp3 (bails out otherwise):
        #
        # Pondering how this can be consolidated with above code to
        # reduce iterating...
        #
        # Just so it's clear, I hate this code (i.e. FIXME).
        #
        for patchid, timestamps in patchidMap.iteritems():
            if len(timestamps) > 1:
                # Untested beyond 2.
                assert(len(timestamps) == 2)
                # FIXME: refactor this monster.
                splitpatch = [ (patch.getAttribute('patchid'),
                                set(patch.packages), patch) for patch in
                               patches if patchidNoRepo(patch.getAttribute('patchid')) == patchid ]
                if splitpatch[0][1].issubset(splitpatch[1][1]):
                    log.info('syncing timestamps (%s %s) ' % (
                        splitpatch[0][2].timestamp,
                        splitpatch[1][2].timestamp) +
                             'across repositories for %s & %s ' % (
                        splitpatch[0][0], splitpatch[1][0]) +
                             'to superset timestamp %s' % splitpatch[1][2].timestamp)
                    splitpatch[0][2].timestamp = splitpatch[1][2].timestamp
                elif splitpatch[1][1].issubset(splitpatch[0][1]):
                    log.info('syncing timestamps (%s %s) ' % (
                        splitpatch[0][2].timestamp,
                        splitpatch[1][2].timestamp) +
                             'across repositories for %s & %s ' % (
                        splitpatch[0][0], splitpatch[1][0]) +
                             'to superset timestamp %s' % splitpatch[0][2].timestamp)
                    splitpatch[1][2].timestamp = splitpatch[0][2].timestamp
                # So far this has only been tested in pure-subset cases.
                else:
                    raise RuntimeError , 'neither %s nor %s is a subset of the other' % (splitpatch[0][0], splitpatch[1][0])

        advPkgMap = {}
        nevras = {}
        packages = {}
        srcPkgAdvMap = {}
        srcPkgPatchidMap = {}

        for patch in patches:
            advisory = patch.getAttribute('patchid')
            patchid = patchidNoRepo(advisory)

            for binPkg in patch.packages:
                nevra = binPkg.getNevra()
                nevraObj = nevras.setdefault(nevra, Nevra(*nevra))
                channelObj = getChannel(binPkg)
                package = Package(channelObj, nevraObj)
                packageObj = packages.setdefault(package, package)
                advPkgMap.setdefault(advisory, set()).add(packageObj)
                srcPkgObj = getSrcPkg(binPkg)
                srcPkgAdvMap.setdefault(srcPkgObj, set()).add(advisory)
                srcPkgPatchidMap.setdefault(srcPkgObj, set()).add(patchid)

                # FIXME: I hate this code too.
                if srcPkgPatchidMap[srcPkgObj] != set([patchid]):
                    # Untested beyond two, and expected case is two
                    # different advisories issued for the same source
                    # package, one each for x86 and x86_64.  (Lots of
                    # these for the kernel, for instance.)
                    assert(len(srcPkgPatchidMap[srcPkgObj]) == 2)
                    srcPkgAdvs = [ getPatchById(patches, srcPkgAdv)
                                   for srcPkgAdv in srcPkgAdvMap[srcPkgObj] ]
                    # Only sync the same source package once.  (It may
                    # appear for multiple binary packages.)
                    if srcPkgAdvs[0].timestamp != srcPkgAdvs[1].timestamp:
                        # Using the min here in case the first advisory
                        # for this source package has already been
                        # published.
                        syncTimestamp = min(srcPkgAdvs[0].timestamp,
                                           srcPkgAdvs[1].timestamp)
                        log.info('syncing timestamps (%s %s) ' % (
                            srcPkgAdvs[0].timestamp, srcPkgAdvs[1].timestamp) +
                                 'across same-SRPM advisories for %s & %s ' % (
                            srcPkgAdvs[0].getAttribute('patchid'),
                            srcPkgAdvs[1].getAttribute('patchid')) +
                                 'to earlier timestamp %s' % syncTimestamp)
                        srcPkgAdvs[0].timestamp = srcPkgAdvs[1].timestamp = syncTimestamp

            # There should be no srcPkgs with more than two patchids.
            assert(len([ x for x, y in srcPkgPatchidMap.iteritems()
                         if len(y) > 2 ]) == 0)

            issue_date = time.strftime('%Y-%m-%d %H:%M:%S',
                                       time.gmtime(int(patch.timestamp)))
            log.info('creating advisory: %s (%s)' % (advisory,
                                                     patch.timestamp))
            adv = Advisory(advisory, patch.summary, issue_date,
                           advPkgMap[advisory])
            self._advisories.add(adv)
            self._advOrder.setdefault(int(patch.timestamp), set()).add(adv)
