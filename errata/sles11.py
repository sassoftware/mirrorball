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
Generate update information based on the patch detail in SuSE repositories
for SLES11.
"""

import time
import logging

from errata.common import Nevra
from errata.common import Package
from errata.common import Channel
from errata.common import Advisory
from errata.sles import AdvisoryManager

log = logging.getLogger('errata')

class AdvisoryManager11(AdvisoryManager):
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
                updateId = bin_timestamp(int(patch.issued))
                # ...or uncomment the below line to disable binning:
                #updateId = int(patch.issued)
                slices.setdefault(updateId,
                                  set()).add(patch.id)
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

        def getSrcPkg(binPkg, binMap):
            srcPkg = binMap[binPkg.getDegenerateNevra()]
            
            if srcPkg:
                return srcPkg
            raise RuntimeError , 'unable to find source package for %s' % binPkg.location

        def getPatchById(patches, patchid):
            for patch in patches:
                if patch.id == patchid:
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
            #for patch in client.getPatchDetail():
            for patch in client.getUpdateInfo():
                for pkg in patch.pkglist:
                    pkg.location = path + '/' + pkg.filename
                # Schema change with SLES11:
                patches.add(patch)

        for label in self._pkgSource._clients:
            self._channels[label] = Channel(label)

        # ...and (time-)slice it up.
        slices = slice(patches)

        for timeslice, patchSet in slices.iteritems():
            for patchId in patchSet:
                patchObj = getPatchById(patches, patchId)
                if patchObj.issued != timeslice:
                    log.info('syncing %s timestamp (%s) to slice timestamp %s' % (
                    patchId, patchObj.issued, timeslice))
                    patchObj.issued = timeslice

        # slices dict is still current since the above only synced the
        # patch timestamps to existing slices.

        # This maps patchid (without regard to repos) to timeslices.
        patchidMap = map_patchids(slices)
        
        # This requires no more than two timestamps per patchid;
        # one each for slessp1 and sdksp1 (bails out otherwise):
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
                splitpatch = [ (patch.id,
                                set([x.filename for x in patch.pkglist]),
                                patch) for patch in
                               patches if patchidNoRepo(patch.id) == patchid ]
                if splitpatch[0][1].issubset(splitpatch[1][1]):
                    log.info('syncing timestamps (%s %s) ' % (
                        splitpatch[0][2].issued,
                        splitpatch[1][2].issued) +
                             'across repositories for %s & %s ' % (
                        splitpatch[0][0], splitpatch[1][0]) +
                             'to superset timestamp %s' % splitpatch[1][2].issued)
                    splitpatch[0][2].issued = splitpatch[1][2].issued
                elif splitpatch[1][1].issubset(splitpatch[0][1]):
                    log.info('syncing timestamps (%s %s) ' % (
                        splitpatch[0][2].issued,
                        splitpatch[1][2].issued) +
                             'across repositories for %s & %s ' % (
                        splitpatch[0][0], splitpatch[1][0]) +
                             'to superset timestamp %s' % splitpatch[0][2].issued)
                    splitpatch[1][2].issued = splitpatch[0][2].issued
                else:
                    maxtime = max(splitpatch[1][2].issued,
                                  splitpatch[0][2].issued)
                    log.info('neither %s nor %s is a subset of the other, syncing timestamps (%s & %s) to later timestamp: %s' % (splitpatch[0][0], splitpatch[1][0], splitpatch[1][2].issued, splitpatch[0][2].issued, maxtime))
                    splitpatch[1][2].issued = splitpatch[0][2].issued = maxtime

        advPkgMap = {}
        nevras = {}
        packages = {}
        srcPkgAdvMap = {}
        srcPkgPatchidMap = {}

        binMap = dict([ (x.getNevra(), y) for x,y in
                        self._pkgSource.binPkgMap.iteritems() ])

        for patch in patches:
            advisory = patch.id
            patchid = patch.id

            for binPkg in patch.pkglist:
                nevra = binPkg.getNevra()
                nevraObj = nevras.setdefault(nevra, Nevra(*nevra))
                channelObj = getChannel(binPkg)
                package = Package(channelObj, nevraObj)
                packageObj = packages.setdefault(package, package)
                advPkgMap.setdefault(advisory, set()).add(packageObj)
                srcPkgObj = getSrcPkg(binPkg, binMap)
                srcPkgAdvMap.setdefault(srcPkgObj, set()).add(advisory)
                srcPkgPatchidMap.setdefault(srcPkgObj, set()).add(patchid)

                # FIXME: I hate this code too.
                # Note that to date this has not been tested in anger
                # on SLES11, as no advisory releases have spanned
                # multiple buckets.
                if srcPkgPatchidMap[srcPkgObj] != set([patchid]):
                    # Untested beyond two, and expected case is two
                    # different advisories issued for the same source
                    # package, one each for x86 and x86_64.  (Lots of
                    # these for the kernel, for instance.)
                    assert(len(srcPkgPatchidMap[srcPkgObj]) == 2)
                    srcPkgAdvs = [ getPatchById(patches, srcPkgAdv)
                                   for srcPkgAdv in srcPkgAdvMap[srcPkgObj] ]
                    syncTimestamp = min([ x.issued for x in srcPkgAdvs ])
                    for srcPkgAdv in srcPkgAdvs:
                        if srcPkgAdv.issued != syncTimestamp:
                            log.info('syncing timestamp (%s) of %s to %s ' % (
                                srcPkgAdv.issued, srcPkgAdv.id, syncTimestamp) +
                                     'across same-SRPM advisories for %s' % (
                                srcPkgAdvs))
                            srcPkgAdv.issued = syncTimestamp
                #import epdb ; epdb.st()

            # There should be no srcPkgs with more than two patchids.
            assert(len([ x for x, y in srcPkgPatchidMap.iteritems()
                         if len(y) > 2 ]) == 0)

        # Now that all timestamps have been munged, make second pass to
        # establish order & create advisories. 
        for patch in patches:
            advisory = patch.id
            
            issue_date = time.strftime('%Y-%m-%d %H:%M:%S',
                                       time.gmtime(int(patch.issued)))
            log.info('creating advisory: %s (%s)' % (advisory,
                                                     patch.issued))
            adv = Advisory(advisory, patch.summary, issue_date,
                           advPkgMap[advisory])
            self._advisories.add(adv)
            self._advOrder.setdefault(int(patch.issued), set()).add(adv)

#        import epdb ; epdb.st()
