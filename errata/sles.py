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

        def getChannel(pkg):
            for label, channel in self._channels.iteritems():
                if label in pkg.location:
                    return channel
            raise RuntimeError , 'unable to find channel for %s' % pkg.location

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

        # ...and (time-)slice it up
        slices = slice(patches)

        for label in self._pkgSource._clients:
            self._channels[label] = Channel(label)
    
        patchmap = {}

        for timestamp, patchids in slices.iteritems():
            for patchid in patchids:
                patchmap.setdefault('-'.join(patchid.split('-')[1:]),
                                    set()).add(timestamp)

        # This requires no more than two timestamps per patchid;
        # one each for slesp3 and sdkp3 (bails out otherwise):
        #
        # Pondering how this can be consolidated with above code to
        # reduce iterating...
        #
        # Also needs tightening up!
        #
        for patchid, timestamps in patchmap.iteritems():
            if len(timestamps) > 1:
                # Untested beyond 2.
                assert(len(timestamps) == 2)
                # FIXME: refactor this monster.
                splitpatch = [ (patch.timestamp, patch.getAttribute('patchid'),
                                set(patch.packages), patch) for patch in
                               patches if '-'.join(patch.getAttribute('patchid').split('-')[1:]) == patchid ]
                if splitpatch[0][2].issubset(splitpatch[1][2]):
                    log.info('syncing timestamps (%s %s) ' % (
                        splitpatch[0][3].timestamp,
                        splitpatch[1][3].timestamp) +
                             'across repositories for %s & %s ' % (
                        splitpatch[0][1], splitpatch[1][1]) +
                             'to superset timestamp %s' % splitpatch[1][3].timestamp)
                    splitpatch[0][3].timestamp = splitpatch[1][3].timestamp
                elif splitpatch[1][2].issubset(splitpatch[0][2]):
                    log.info('syncing timestamps (%s %s) ' % (
                        splitpatch[0][3].timestamp,
                        splitpatch[1][3].timestamp) +
                             'across repositories for %s & %s ' % (
                        splitpatch[0][1], splitpatch[1][1]) +
                             'to superset timestamp %s' % splitpatch[0][3].timestamp)
                    splitpatch[1][3].timestamp = splitpatch[0][3].timestamp
                # So far this has only been tested in pure-subset cases.
                else:
                    raise RuntimeError , 'neither %s nor %s is a subset of the other' % (splitpatch[0][1], splitpatch[1][1])

        advPkgMap = {}
        nevras = {}
        packages = {}
        
        for patch in patches:
            advisory = patch.getAttribute('patchid')
            issue_date = time.strftime('%Y-%m-%d %H:%M:%S',
                                       time.gmtime(int(patch.timestamp)))

            for binPkg in patch.packages:
                nevra = binPkg.getNevra()
                nevraObj = nevras.setdefault(nevra, Nevra(*nevra))
                channelObj = getChannel(binPkg)
                package = Package(channelObj, nevraObj)
                packageObj = packages.setdefault(package, package)
                advPkgMap.setdefault(advisory, set()).add(packageObj)

            log.info('creating advisory: %s' % advisory)
            adv = Advisory(advisory, patch.summary, issue_date,
                           advPkgMap[advisory])
            self._advisories.add(adv)
            self._advOrder.setdefault(int(patch.timestamp), set()).add(adv)

        import epdb ; epdb.st()
