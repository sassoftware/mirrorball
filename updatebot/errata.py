#
# Copyright (c) 2009 rPath, Inc.
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
Module for ordering errata.
"""

import time
import logging

from updatebot.errors import ErrataPackageNotFoundError

log = logging.getLogger('updatebot.errata')

def loadErrata(func):
    def wrapper(self, *args, **kwargs):
        if not self._order:
            self._orderErrata()
        return func(self, *args, **kwargs)
    return wrapper

class ErrataFilter(object):
    """
    Filter data from a given errataSource in chronological order.
    """

    def __init__(self, pkgSource, errataSource):
        self._pkgSource = pkgSource
        self._errata = errataSource

        self._order = {}
        self._advMap = {}

    @loadErrata
    def getInitialPackages(self):
        """
        Get the initial set of packages.
        """

        return self._order[0]

    @loadErrata
    def getUpdateDetail(self, bucketId):
        """
        Given a errata timestamp lookup the name and summary.
        """

        return self._advMap.get(bucketId, None)

    @loadErrata
    def getUpdateDetailMessage(self, bucketId):
        """
        Given a errata timestamp create a name and summary message.
        """

        if bucketId in self._advMap:
            msg = ''
            for adv in self._advMap[bucketId]:
                msg += '(%(name)s: %(summary)s) ' % adv
            return msg
        else:
            return '%s (no detail found)' % bucketId

    @loadErrata
    def iterByIssueDate(self, start=None):
        """
        Yield sets of srcPkgs by errata release date.
        @param start: timestamp from which to start iterating.
        @type start: int
        """

        for stamp in sorted(self._order.keys()):
            if start > stamp:
                continue
            yield stamp, self._order[stamp]

    def _orderErrata(self):
        """
        Order errata by timestamp.
        """

        # order packages by errata release
        buckets, other = self._sortPackagesByErrataTimestamp()

        # insert packages that did not have errata and were not in the initial
        # set of packages (golden bits)
        srcMap = {}
        for pkg in other:
            src = self._pkgSource.binPkgMap[pkg]
            if src not in srcMap:
                srcMap[src] = []
            srcMap[src].append(pkg)

        # insert bins by buildstamp
        for src, bins in srcMap.iteritems():
            buildstamp = int(sorted(bins)[0].buildTimestamp)
            if buildstamp not in buckets:
                buckets[buildstamp] = []
            buckets[buildstamp].extend(bins)

        # get sources to build
        for bucketId in sorted(buckets.keys()):
            bucket = buckets[bucketId]
            self._order[bucketId] = set()
            for pkg in bucket:
                src = self._pkgSource.binPkgMap[pkg]
                self._order[bucketId].add(src)

    def _getNevra(self, pkg):
        """
        Get the NEVRA of a package object and do any transformation required.
        """

        # convert nevra to yum compatible nevra
        nevra = list(pkg.getNevra())
        if nevra[1] is None:
            nevra[1] = '0'
        if type(nevra[1]) == int:
            nevra[1] = str(nevra[1])
        nevra = tuple(nevra)

        return nevra

    def _sortPackagesByErrataTimestamp(self):
        """
        Sort packages by errata release timestamp.
        """

        # get mapping of nevra to pkg obj
        nevras = dict(((x.name, x.epoch, x.version, x.release, x.arch), x)
                      for x in self._pkgSource.binPkgMap.keys()
                        if x.arch != 'src' and '-debuginfo' not in x.name)

        # pull nevras into errata sized buckets
        buckets = {}
        nevraMap = {}

        log.info('processing errata')

        indexedChannels = set(self._errata.getChannels())
        arches = ('i386', 'i486', 'i586', 'i686', 'x86_64', 'noarch')
        for e in self._errata.iterByIssueDate():
            bucket = []
            allocated = []
            bucketId = None
            #log.info('processing %s' % e.advisory)
            for pkg in e.packages:
                nevra = self._getNevra(pkg)

                # ignore arches we don't know about.
                if nevra[4] not in arches:
                    continue

                # filter out channels we don't have indexed
                channels = set([ x.label for x in pkg.channels ])
                if not indexedChannels & channels:
                    continue

                # move nevra to errata buckets
                if nevra in nevras:
                    binPkg = nevras.pop(nevra)
                    bucket.append(binPkg)
                    allocated.append(nevra)

                # nevra is already part of another bucket
                elif nevra in nevraMap:
                    bucketId = nevraMap[nevra]

                # raise error if we can't find the required package
                else:
                    raise ErrataPackageNotFoundError(pkg=nevra)

            if bucketId is None:
                bucketId = int(time.mktime(time.strptime(e.issue_date,
                                                         '%Y-%m-%d %H:%M:%S')))
                buckets[bucketId] = bucket
            else:
                buckets[bucketId].extend(bucket)

            for nevra in allocated:
                nevraMap[nevra] = bucketId

            if bucketId not in self._advMap:
                self._advMap[bucketId] = set()
            self._advMap[bucketId].add({'name': e.advisory,
                                        'summary': e.synopsis})

        # separate out golden bits
        other = []
        golden = []
        firstErrata = sorted(buckets.keys())[0]
        for nevra, pkg in nevras.iteritems():
            buildtime = int(pkg.buildTimestamp)
            if buildtime < firstErrata:
                golden.append(pkg)
            else:
                other.append(pkg)

        buckets[0] = golden

        return buckets, other
