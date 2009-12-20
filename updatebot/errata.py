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
from updatebot.errors import ErrataSourceDataMissingError

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

    def __init__(self, cfg, pkgSource, errataSource):
        self._cfg = cfg
        self._pkgSource = pkgSource
        self._errata = errataSource

        # timestamp: srcPkg Set
        self._order = {}

        # timestamp: advisory info
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

        return [ dict(x) for x in self._advMap.get(bucketId, tuple()) ]

    @loadErrata
    def getUpdateDetailMessage(self, bucketId):
        """
        Given a errata timestamp create a name and summary message.
        """

        if bucketId in self._advMap:
            msg = ''
            for adv in self._advMap[bucketId]:
                msg += '(%(name)s: %(summary)s) ' % dict(adv)
            return msg
        else:
            return '%s (no detail found)' % bucketId

    @loadErrata
    def iterByIssueDate(self, current=None):
        """
        Yield sets of srcPkgs by errata release date.
        @param current: the current state, start iterating after this state has
                        been reached.
        @type current: int
        """

        for stamp in sorted(self._order.keys()):
            if current >= stamp:
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

        # fold together updates to preserve dep closure.
        for mergeList in self._cfg.mergeUpdates:
            target = mergeList[0]
            # merge remaining updates into target.
            for source in mergeList[1:]:
                log.info('merging errata bucket %s -> %s' % (source, target))
                updateSet = self._order.pop(source)
                oldNames = set([ x.name for x in self._order[target]])
                newNames = set([ x.name for x in updateSet ])
                # Check for overlapping updates. If there is overlap, these
                # things can't be merged since all versions need to be
                # represented in the repository.
                if oldNames & newNames:
                    raise UnableToMergeUpdatesError(
                        source=source, target=target,
                        package=', '.join(oldNames & newNames)
                    )
                self._order[target].update(updateSet)

                # merge advisory detail.
                if source in self._advMap:
                    advInfo = self._advMap.pop(source)
                    if target not in self._advMap:
                        self._advMap[target] = set()
                    self._advMap[target].update(advInfo)

        # reschedule any updates that may have been released out of order.
        for source, dest in self._cfg.reorderUpdates:
            # Probably don't want to move an update into an already
            # existing bucket.
            assert dest not in self._order

            log.info('rescheduling %s -> %s' % (source, dest))

            # remove old version
            bucket = self._order.pop(source)
            adv = self._advMap.pop(source)

            # move to new version
            self._order[dest] = bucket
            self._advMap[dest] = adv

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
        broken = []
        buckets = {}
        nevraMap = {}

        log.info('processing errata')

        indexedChannels = set(self._errata.getChannels())
        # FIXME: This should not be a hard coded set of arches.
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

            # There should be packages in the bucket or the packages should
            # already be in an existing bucket (bucketId != None), if there
            # aren't the errata store is probably broken.
            if not bucket and bucketId is None:
                broken.append(e.advisory)
                log.critical('broken advisory: %s' % e.advisory)
                continue

            if bucketId is None:
                bucketId = int(time.mktime(time.strptime(e.issue_date,
                                                         '%Y-%m-%d %H:%M:%S')))

            if bucketId not in buckets:
                buckets[bucketId] = set()
            buckets[bucketId].update(bucket)

            for nevra in allocated:
                nevraMap[nevra] = bucketId

            if bucketId not in self._advMap:
                self._advMap[bucketId] = set()
            self._advMap[bucketId].add((('name', e.advisory),
                                        ('summary', e.synopsis)))

        if broken:
            raise ErrataSourceDataMissingError(broken=broken)

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
