#
# Copyright (c) 2011 rPath, Inc.
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

import datetime
import os
import copy
import time
import logging
from dateutil import parser as dateutil_parser
from dateutil import tz as dateutil_tz

from updatebot import update
from updatebot import conaryhelper
from updatebot.errors import MissingErrataError
from updatebot.errors import ErrataPackageNotFoundError
from updatebot.errors import ErrataSourceDataMissingError
from updatebot.errors import PackageNotFoundInBucketError
from updatebot.errors import AdvisoryPackageMissingFromBucketError

# update errors
from updatebot.errors import UpdateGoesBackwardsError
from updatebot.errors import UpdateRemovesPackageError
from updatebot.errors import UpdateReusesPackageError

# Fix default type of _findTrovesCache
from updatebot.lib.findtroves import FindTrovesCache

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

    def __init__(self, cfg, ui, pkgSource, errataSource):
        self._cfg = cfg
        self._ui = ui
        self._pkgSource = pkgSource
        self._errata = errataSource

        # timestamp: srcPkg Set
        self._order = {}

        # timestamp: advisory info
        self._advMap = {}

        # advisory: nevras
        self._advPkgMap = {}

        # nevra: advisories
        self._advPkgRevMap = {}

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
    def getAdvisoryPackages(self, advisory):
        """
        Give a valid advisory name, return a set of applicable source package
        objects.
        """

        return self._advPkgMap.get(advisory, set())

    @loadErrata
    def getVersions(self, bucketId):
        """
        Get a set of group versions that should be built for the given bucketId.
        @param bucketId: identifier for a given update slice
        @type bucketId: integer (unix time)
        """

        versions = dict()
        for advInfo in self.getUpdateDetail(bucketId):
            advisory = advInfo['name']
            versions[advisory] = self._errata.getGroupVersion(advisory)
        return versions

    @loadErrata
    def getNames(self, bucketId):
        """
        Get a map of group names by advisory.
        """

        names = dict()
        for advInfo in self.getUpdateDetail(bucketId):
            advisory = advInfo['name']
            names[advisory] = self._errata.getGroupName(advisory)
        return names

    def getBucketVersion(self, bucketId):
        """
        Convert a bucketId to a conary version.
        @param bucketId: identifier for a given update slice
        @type bucketId: integer (unix time)
        """

        version = self._cfg.upstreamVersionMap.get(bucketId, None)
        if not version:
            version = time.strftime('%Y.%m.%d_%H%M.%S', time.gmtime(bucketId))

        return version

    @loadErrata
    def getModifiedErrata(self, current):
        """
        Get all updates that were issued before current, but have been modified
        after current.
        @param current: the current state, start iterating after this state has
                        been reached.
        @type current: int
        """

        # Get modified errata from the model
        modified = self._errata.getModifiedErrata(current)

        # Map this errata to srpms
        modMap = {}
        for e in modified:
            advisory = e.advisory
            last_modified = e.last_modified_date
            issue_date = e.issue_date
            pkgs = self._advPkgMap[advisory]

            assert advisory not in modMap

            modMap[advisory] = {
                'advisory': advisory,
                'last_modified': last_modified,
                'issue_date': issue_date,
                'srpms': pkgs,
            }

        return modMap

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

    @loadErrata
    def sanityCheckOrder(self):
        """
        Validate the update order for:
            1. package revisions going backwards
            2. packages being removed
            3. same package in bucket multiple times
            4. obsolete packages still included in groups
        Raise an exception if sanity checks are not satisfied.
        """

        log.info('sanity checking ordering')

        def tconv(stamp):
            return time.strftime('%m-%d-%Y %H:%M:%S', time.gmtime(stamp))

        def rhnUrl(errataId):
            errataId = errataId.replace(':', '-')
            return 'http://rhn.redhat.com/errata/%s.html' % errataId

        def rhnUrls(errataSet):
            return ' '.join(rhnUrl(x) for x in errataSet)

        # duplicate updater and pkgsource so as to not change state.
        pkgSource = copy.copy(self._pkgSource)
        updater = update.Updater(self._cfg, self._ui, pkgSource)
        updater._conaryhelper = _ConaryHelperShim(self._cfg)

        if self._cfg.platformSearchPath:
            log.info('prefetching sources for parent platform labels')
            for label in self._cfg.platformSearchPath:
                updater._conaryhelper.cacheSources(label, latest=False)
            log.info('prefetching findTroves information for parent platform '
                     'labels')
            updater._conaryhelper.populateFindTrovesCache(
                self._cfg.platformSearchPath)

        # build a mapping of srpm to bucketId for debuging purposes
        srpmToBucketId = {}
        for bucketId, srpms in self._order.iteritems():
            for srpm in srpms:
                srpmToBucketId[srpm] = bucketId

        # build a mapping of srpm to advisory for debuging purposes
        srpmToAdvisory = {}
        for advisory, srpms in self._advPkgMap.iteritems():
            for srpm in srpms:
                srpmToAdvisory.setdefault(srpm, set()).add(advisory)

        # convert keepObsolete config into set of edges
        keepObsolete = set(self._cfg.keepObsolete)
        keepObsoleteSource = set(self._cfg.keepObsoleteSource)

        errors = {}
        # Make sure there no buckets that contain the same srpm name twice.
        for updateId, srpms in sorted(self._order.iteritems()):
            seen = {}
            dups = {}
            for srpm in srpms:
                if srpm.name in seen:
                    thisdup = dups.setdefault(srpm.name, set())
                    thisdup.add(seen[srpm.name])
                    thisdup.add(srpm)
                else:
                    seen[srpm.name] = srpm
                    continue
            if dups:
                log.error('found duplicates in %s' % updateId)
                errors.setdefault(updateId, []).append(('duplicates', dups))

        # Play though entire update history to check for iregularities.
        current = {}
        childPackages = []
        parentPackages = []
        removals = self._cfg.updateRemovesPackages
        replaces = self._cfg.updateReplacesPackages
        downgraded = self._cfg.allowPackageDowngrades
        currentlyRemovedBinaryNevras = set()
        foundObsoleteEdges = set()
        foundObsoleteSrcs = set()
        for updateId in sorted(self._order.keys()):
            log.info('validating %s' % updateId)
            expectedRemovals = removals.get(updateId, [])
            expectedReplaces = replaces.get(updateId, [])
            expectedKeepRemovals = self._cfg.keepRemoved.get(updateId, [])
            explicitSourceRemovals = self._cfg.removeSource.get(updateId, set())
            explicitBinaryRemovals = self._cfg.removeObsoleted.get(updateId, set())
            explicitIgnoreSources = self._cfg.ignoreSourceUpdate.get(updateId, set())
            if explicitIgnoreSources:
                log.info('explicitly ignoring %s in update %s' %
                         (explicitIgnoreSources, updateId))
            explicitPackageDowngrades = downgraded.get(updateId, None)

            assert len(self._order[updateId])
            for srpm in self._order[updateId]:
                nvf = (srpm.name, None, None)

                # validate updates
                try:
                    toUpdate = updater._sanitizeTrove(nvf, srpm,
                        expectedRemovals=expectedRemovals + expectedReplaces,
                        allowPackageDowngrades=explicitPackageDowngrades,
                        keepRemovedPackages=expectedKeepRemovals)

                    # If a source was manually added to this updateId it may
                    # have already been part of another update, which would
                    # cause the manifest not to change.
                    if (srpm.getNevra() not in
                        self._cfg.addSource.get(updateId, [])):
                        assert toUpdate

                except (UpdateGoesBackwardsError,
                        UpdateRemovesPackageError,
                        UpdateReusesPackageError), e:
                    errors.setdefault(updateId, []).append(e)

                # apply update to checkout
                if srpm.getNevra() in explicitSourceRemovals:
                    log.error('Removing %s in %s would cause it never to be promoted' %
                              (str(' '.join(srpm.getNevra())), updateId))

                if srpm.getNevra() in explicitIgnoreSources:
                    log.warn('Ignoring %s in %s will cause it never to be promoted' %
                             (str(' '.join(srpm.getNevra())), updateId))
                else:
                    current[srpm.name] = srpm
                    version = updater.update(nvf, srpm)
                    assert (not version or
                            not updater.isPlatformTrove(version))
                    if version:
                        parentPackages.append(((nvf, srpm), version))
                    else:
                        childPackages.append(((nvf, srpm), None))

            # all package names obsoleted by packages in the current set
            obsoleteNames = set()
            obsoleteBinaries = set()
            obsoleteSources = set()
            obsoletingPkgMap = {}
            pkgNames = set()
            pkgNameMap = {}
            srpmNameMap = {}
            # Create maps for processing obsoletes
            for srpm in sorted(current.itervalues()):
                if srpm.getNevra() in explicitSourceRemovals:
                    current.pop(srpm.name, None)
                    continue
                if srpm.getNevra() in explicitIgnoreSources:
                    log.info('explicitly ignoring source package update %s' % [explicitIgnoreSources])
                    continue
                for pkg in sorted(self._pkgSource.srcPkgMap[srpm]):
                    if pkg.arch == 'src':
                        continue
                    pkgNames.add(pkg.name)
                    pkgNameMap[pkg.name] = pkg
                    if pkg in self._pkgSource.obsoletesMap:
                        pkgObsoleteNames = self._pkgSource.obsoletesMap[pkg]
                        for obsoleteName in pkgObsoleteNames:
                            obsoletingPkgMap[obsoleteName] = pkg
                            obsoleteNames.add(obsoleteName)

            # packages that really moved from one source to another
            removedShouldBeReplaced = set(expectedRemovals) & pkgNames

            for obsoleteName in explicitBinaryRemovals:
                # these nevra-nevra edges are already handled in config,
                # do not report them in the wrong bucket
                obsoletingPkg = obsoletingPkgMap[obsoleteName]
                obsoletedPkg = pkgNameMap[obsoleteName]
                obsoleteEdge = (obsoletingPkg, obsoletedPkg)
                foundObsoleteEdges.add(obsoleteEdge)

            # coalesce obsoleted packages by src package, filtering
            # by explicit configs
            obsoletePkgMap = {}
            for obsoleteName in obsoleteNames:
                if obsoleteName in pkgNames:
                    obsoletingPkg = obsoletingPkgMap[obsoleteName]
                    obsoletedPkg = pkgNameMap[obsoleteName]
                    obsoleteNevraEdge = (obsoletingPkg.getNevra(),
                                         obsoletedPkg.getNevra())

                    if obsoleteNevraEdge in keepObsolete:
                        # We have configured to keep this "obsolete" package
                        continue

                    obsoleteEdge = (obsoletingPkg, obsoletedPkg)
                    if obsoleteEdge in foundObsoleteEdges:
                        # report each obsoleting relationship only once
                        continue
                    foundObsoleteEdges.add(obsoleteEdge)

                    obsoleteSrcPkg = self._pkgSource.binPkgMap[obsoletedPkg]
                    obsoletePkgMap.setdefault(obsoleteSrcPkg,
                                              set()).add(obsoleteEdge)

            # report sets of obsoleted packages inappropriately included
            for srcPkg, obsoleteEdgeSet in sorted(obsoletePkgMap.iteritems()):
                # determine whether bins or srcs need removal
                pkgsBySrc = self._pkgSource.srcPkgMap[srcPkg]
                binPkgs = tuple(sorted(set(x for x in
                    pkgsBySrc if x.arch != 'src')))
                unremovedBinPkgs = tuple(sorted(set(x for x in
                    pkgsBySrc if x.arch != 'src'
                              and x.name not in obsoleteNames)))

                if unremovedBinPkgs:
                    obsoleteBinaries.add(
                        (tuple(sorted(obsoleteEdgeSet)),
                         srcPkg,
                         binPkgs,
                         unremovedBinPkgs))
                else:
                    # choose whether to include or exclude pkg sets by sources
                    if srcPkg not in foundObsoleteSrcs:
                        obsoletingSrcPkgs = tuple(sorted(set(
                            self._pkgSource.binPkgMap[x]
                            for x, y in obsoleteEdgeSet)))

                        newEdgeSet = set()
                        obsoletingSrcPkgs = set()

                        for obsoletingPkg, obsoletedPkg in obsoleteEdgeSet:
                            obsoletingSrcPkg = self._pkgSource.binPkgMap[obsoletingPkg]
                            if (obsoletingSrcPkg.getNevra(), srcPkg.getNevra()) in keepObsoleteSource:
                                continue
                            newEdgeSet.add((obsoletingPkg, obsoletedPkg))
                            obsoletingSrcPkgs.add(obsoletingSrcPkg)

                        if newEdgeSet:
                            # we exclude any source only once, not per bucket
                            for obsoletingPkg, obsoletedPkg in newEdgeSet:
                                obsoleteSources.add(
                                    (obsoletedPkg.name,
                                     obsoletedPkg,
                                     tuple(obsoletingSrcPkgs),
                                     srcPkg,
                                     binPkgs))

                            foundObsoleteSrcs.add(srcPkg)


            if obsoleteBinaries:
                log.error('found obsolete binary packages in %s' % updateId)
                errors.setdefault(updateId, []).append(('obsoleteBinaries',
                                                        obsoleteBinaries))
            if obsoleteSources:
                log.error('found obsolete source packages in %s' % updateId)
                errors.setdefault(updateId, []).append(('obsoleteSources',
                                                        obsoleteSources))
            if removedShouldBeReplaced:
                log.error('found removals for replacements in %s' % updateId)
                errors.setdefault(updateId, []).append(('removedShouldBeReplaced',
                                                        removedShouldBeReplaced))

        # Report errors.
        for updateId, error in sorted(errors.iteritems()):
            for e in error:
                if isinstance(e, UpdateGoesBackwardsError):
                    one, two = e.why
                    oneNevra = str(' '.join(one.getNevra()))
                    twoNevra = str(' '.join(two.getNevra()))
                    log.error('%s %s -revertsTo-> %s' % (updateId,
                             oneNevra, twoNevra))
                    if one in srpmToAdvisory and two in srpmToAdvisory:
                        log.info('%s -revertsTo-> %s' % (
                                 rhnUrls(srpmToAdvisory[one]),
                                 rhnUrls(srpmToAdvisory[two])))
                    if one in srpmToBucketId and two in srpmToBucketId:
                        log.info('%s %s (%d) -> %s (%d)' % (updateId,
                                 tconv(srpmToBucketId[one]), srpmToBucketId[one],
                                 tconv(srpmToBucketId[two]), srpmToBucketId[two]))
                        log.info('? reorderSource %s otherId<%s %s' % (
                            updateId, srpmToBucketId[one], twoNevra))
                    for errataId in srpmToAdvisory.get(two, []):
                        log.info('? reorderAdvisory %s otherId<%s %s' % (
                            updateId, srpmToBucketId[one], errataId))
                elif isinstance(e, UpdateReusesPackageError):
                    # Note that updateObsoletesPackages not yet implemented...
                    log.error('%s %s reused in %s; check for obsoletes?' % (
                             updateId, e.pkgNames, e.newspkg))
                    for name in sorted(set(p.name for p in e.pkgList)):
                        log.info('? updateObsoletesPackages %s %s' % (
                                 updateId, name))
                elif isinstance(e, UpdateRemovesPackageError):
                    log.error('%s %s removed in %s' % (
                             updateId, e.pkgNames, e.newspkg))
                    for name, p in sorted(dict((p.name, p) for p in e.pkgList).items()):
                        log.info('? updateRemovesPackages %s %s' % (
                                 updateId, name))
                        log.info('? keepRemoved %s %s' % (updateId, '%s %s %s %s %s' % p.getNevra()))
                elif isinstance(e, tuple):
                    if e[0] == 'duplicates':
                        sortedOrder = sorted(self._order)
                        previousId = sortedOrder[sortedOrder.index(updateId)-1]
                        nextId = sortedOrder[sortedOrder.index(updateId)+1]
                        for dupName, dupSet in e[1].iteritems():
                            dupList = sorted(dupSet)
                            log.error('%s contains duplicate %s %s' %(updateId,
                                dupName, dupList))
                            # Changing to use older pkgs to make msg
                            for srcPkg in sorted(dupList[1:]):
                                srcNevra = str(' '.join(srcPkg.getNevra()))
                                if srcPkg in srpmToAdvisory:
                                    log.info('%s : %s' % (
                                        srcNevra, rhnUrls(srpmToAdvisory[srcPkg])))
                                log.info('? reorderSource %s earlierId> %s %s' %
                                    (updateId, previousId, srcNevra))
                                log.info('? reorderSource %s laterId> %s %s' %
                                    (updateId, nextId, srcNevra))
                                for errataId in srpmToAdvisory.get(srcPkg, []):
                                    log.info(
                                        '? reorderAdvisory %s earlierId> %s %r'
                                        % (updateId, previousId, errataId))
                                    log.info(
                                        '? reorderAdvisory %s laterId> %s %r'
                                        % (updateId, nextId, errataId))

                    elif e[0] == 'obsoleteBinaries':
                        for (obsoleteEdgeList, srcPkg, binPkgs,
                             unremovedBinPkgs) in e[1]:
                            obsoletingNevra = str(' '.join(obsoletingPkg.getNevra()))
                            obsoletedNevra = str(' '.join(obsoletedPkg.getNevra()))
                            srcNevra = srcPkg.getNevra()
                            srcNevraStr = str(' '.join(srcNevra))
                            unremovedStr = str(' '.join(sorted(
                                                    repr(x) for x in unremovedBinPkgs)))
                            obsoleteNames = set()
                            for obsoleteEdge in obsoleteEdgeList:
                                obsoletingPkg, obsoletedPkg = obsoleteEdge
                                obsoletingNevra = str(' '.join(obsoletingPkg.getNevra()))
                                obsoletedNevra = str(' '.join(obsoletedPkg.getNevra()))
                                obsoleteName = obsoletedPkg.name
                                obsoleteNames.add(obsoleteName)
                                log.error('%s %s obsoletes %s (%s)' % (
                                         updateId, obsoletingPkg,
                                         obsoletedPkg, obsoleteName))
                                log.info('? keepObsolete %s %s' %
                                         (obsoletingNevra, obsoletedNevra))
                                log.info('? removeObsoleted %s %s' % (updateId,
                                         obsoleteName))
                            log.error('Not "removeSource %s"; that would remove non-obsoleted %s' %
                                     (srcNevraStr, unremovedStr))

                    elif e[0] == 'obsoleteSources':
                        for (obsoleteName, obsoletedPkg, obsoletingSrcPkgs,
                             srcPkg, binPkgs) in e[1]:
                            srcNevra = srcPkg.getNevra()
                            srcNevraStr = str(' '.join(srcNevra))
                            obsoletingSrcPkgNames = str(' '.join(sorted(set(
                                x.name for x in obsoletingSrcPkgs))))
                            pkgList = str(' '.join(repr(x) for x in binPkgs))
                            log.error('%s %s obsolete(s) %s (%s)' % (
                                     updateId, obsoletingSrcPkgNames,
                                     obsoletedPkg, obsoleteName))
                            log.info('? removeSource %s %s # %s' % (
                                     updateId, srcNevraStr,
                                     obsoletingSrcPkgNames))
                            for obsoletingSrcPkg in obsoletingSrcPkgs:
                                log.info('? keepObsoleteSource %s %s'
                                  % (str(' '.join(obsoletingSrcPkg.getNevra())),
                                     srcNevraStr))
                            log.info(' will remove the following: %s' % pkgList)
                    elif e[0] == 'removedShouldBeReplaced':
                        for pkgName in e[1]:
                            log.error('%s removed package %s should be replaced' % (
                                     updateId, pkgName))
                            log.info('? updateReplacesPackages %s %s' % (
                                     updateId, pkgName))

        # Clear the cache since it would be dirty at this point.
        updater._conaryhelper.clearCache()

        # Fail if there are any errors.
        assert not errors

        log.info('order sanity checking complete')

        return childPackages, parentPackages

    def _orderErrata(self):
        """
        Order errata by timestamp.
        """

        # order packages by errata release
        buckets, other = self._sortPackagesByErrataTimestamp()

        # insert packages that did not have errata and were not in the initial
        # set of packages (golden bits)
        srcMap = {}
        missing = set()
        for pkg in other:
            if pkg.getNevra() not in self._cfg.allowMissingErrata:
                missing.add(pkg)

            src = self._pkgSource.binPkgMap[pkg]
            srcMap.setdefault(src, list()).append(pkg)

        # Raise an error if there are any packages missing an errata that are
        # now explicitly allowed by the config.
        if missing:
            raise MissingErrataError(packages=list(missing))

        # insert bins by buildstamp
        extras = {}

        # Build a reverse map of broken errata so that we can match packages
        # and advisories
        nevraAdvMap = {}
        for adv, nevras in self._cfg.brokenErrata.iteritems():
            for nevra in nevras:
                assert nevra not in nevraAdvMap
                nevraAdvMap[nevra] = adv

        # Build reverse map of advisory to bucketId.
        advRevMap = {}
        for bucketId, advInfoList in self._advMap.iteritems():
            for advInfo in advInfoList:
                advDict = dict(advInfo)
                assert advDict['name'] not in advRevMap
                advRevMap[advDict['name']] = bucketId

        for src, bins in srcMap.iteritems():
            # Pull out any package sets that look like they are incomplete.
            if len(bins) != len(set([ (x.name, x.arch) for x in self._pkgSource.srcPkgMap[src] ])) - 1:
                extras[src] = bins
                continue

            if src.getNevra() in nevraAdvMap:
                advisory = nevraAdvMap[src.getNevra()]
                bucketId = advRevMap[advisory]
                log.info('inserting %s for advisory %s into bucket %s'
                         % (src, advisory, bucketId))
                buckets.setdefault(bucketId, set()).add(src)
                continue

            buildstamp = int(sorted(bins)[0].buildTimestamp)
            buckets.setdefault(buildstamp, set()).update(set(bins))

        # get sources to build
        srpmToBucketId = {}
        for bucketId in sorted(buckets.keys()):
            bucket = buckets[bucketId]
            self._order[bucketId] = set()
            for pkg in bucket:
                src = self._pkgSource.binPkgMap[pkg]
                self._order[bucketId].add(src)
                srpmToBucketId[src] = bucketId

        # Make sure extra packages are already included in the order.
        for src, bins in extras.iteritems():
            assert src in srpmToBucketId
            assert src in self._order[srpmToBucketId[src]]
            for bin in bins:
                assert bin in self._pkgSource.srcPkgMap[src]

        self._handleLastErrata()
        
        ##
        # Start order munging here
        ##

        # Remove any source packages we're deliberately ignoring:
        # Note that we do this before we check for drops, as some drops
        # are deliberate.
        ignoredCount = 0
        for source, nevras in self._cfg.ignoreSourceUpdate.iteritems():
            for nevra in nevras:
                self._reorderSource(source, None, nevra)
                ignoredCount += 1

        # Make sure we don't drop any updates
        totalPkgs = sum([ len(x) for x in self._order.itervalues() ])
        pkgs = set()
        for pkgSet in self._order.itervalues():
            pkgs.update(pkgSet)

        # This assert validates that no one srpm is mentioned in more than
        # one bucket. This can happen when a partial set of packages was
        # released and the code tried to fill in the other packages by build
        # time.
        #
        # This has to be commented out for SLES11e due to a reissuing
        # of python-base as an update (when it was already provided in
        # the base).
        # Need to work around this programmatically.
        #
        # assert len(pkgs) == totalPkgs

        # fold together updates to preserve dep closure.
        for mergeList in self._cfg.mergeUpdates:
            self._mergeUpdates(mergeList)

        # reschedule any updates that may have been released out of order.
        for source, dest in self._cfg.reorderUpdates:
            self._reorderUpdates(source, dest)

        # reschedule any individual advisories.
        for source, dest, advisory in self._cfg.reorderAdvisory:
            self._reorderAdvisory(source, dest, advisory)

        # reschedule individual packages
        for source, dest, nevra in self._cfg.reorderSource:
            self._reorderSource(source, dest, nevra)

        # add a source to a specific bucket, used to "promote" newer versions
        # forward.
        nevras = dict([ (x.getNevra(), x)
                         for x in self._pkgSource.srcPkgMap ])
        diffCount = 0
        for updateId, srcNevras in self._cfg.addSource.iteritems():
            sources = set(nevras[x] for x in srcNevras)
            self._order.setdefault(updateId, set()).update(sources)
            diffCount += len(srcNevras)

        # Make sure we don't drop any updates
        totalPkgs2 = sum([ len(x) for x in self._order.itervalues() ])
        pkgs = set()
        for pkgSet in self._order.itervalues():
            pkgs.update(pkgSet)
        # assert len(pkgs) == totalPkgs2 - diffCount
        # assert totalPkgs2 == totalPkgs + diffCount

        # pop off future updates
        for x in self._order.keys():
            if int(x) > time.time():
                 self._order.pop(x)
                 if self._advMap.has_key(x):
                     self._advMap.pop(x)

    def _mergeUpdates(self, mergeList):
        """
        Merge a list of updates into one bucket.
        """

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
                log.warn('merge causes package overlap')
            self._order[target].update(updateSet)

            # merge advisory detail.
            if source in self._advMap:
                advInfo = self._advMap.pop(source)
                if target not in self._advMap:
                    self._advMap[target] = set()
                self._advMap[target].update(advInfo)

    def _handleLastErrata(self):
        """
        Remove timestamps past the configured lastErrata to prevent
        processing them.
        """
        if self._cfg.lastErrata:
            log.info('handling configured lastErrata (%s)' %
                     self._cfg.lastErrata)
            updateIds = [ x for x in self._order.iterkeys() ]
            for x in updateIds:
                if x > self._cfg.lastErrata:
                    log.info('unsequencing timestamp %s (> %s)' %
                             (x, self._cfg.lastErrata))
                    del self._order[x]

    def _reorderUpdates(self, source, dest):
        """
        Reschedule an update from one timestamp to another.
        """

        # Probably don't want to move an update into an already
        # existing bucket.
        assert dest not in self._order

        log.info('rescheduling %s -> %s' % (source, dest))

        # remove old version
        bucket = self._order.pop(source)
        # There will not be an entry for sources that do not have
        # advisories, default to None.
        adv = self._advMap.pop(source, None)

        # move to new version
        self._order[dest] = bucket
        if adv: self._advMap[dest] = adv


    def _reorderAdvisory(self, source, dest, advisory):
        """
        Reschedule a single advisory.
        """

        log.info('rescheduling %s %s -> %s' % (advisory, source, dest))

        # Find the srpms that apply to this advisory
        srpms = self._advPkgMap[advisory]

        # Remove them from the source bucket Id, while making sure they are
        # all in the source bucketId.
        bucketNevras = dict([ (x.getNevra(), x)
                              for x in self._order[source] ])

        for srpm in srpms:
            # Make sure to only move packages if they haven't already
            # been moved.
            if (srpm not in self._order[source] and
                dest in self._order and
                srpm in self._order[dest]):
                continue

            nevra = srpm.getNevra()

            if nevra not in bucketNevras:
                raise AdvisoryPackageMissingFromBucketError(nevra=nevra)
            self._order[source].remove(srpm)
            if not len(self._order[source]):
                del self._order[source]

            # Make sure that each package that we are moving is only
            # mentioned in one advisory.
            advisories = self._advPkgRevMap[srpm]
            if len(advisories) > 1:
                advisories = advisories.difference(set(advisory))
                # Make sure all advisories this srpm is mentioned in are also
                # scheduled to be moved to the same bucket.
                for adv in advisories:
                    assert (source, dest, adv) in self._cfg.reorderAdvisory

            # Move packages to destination bucket Id.
            self._order.setdefault(dest, set()).add(srpm)

        # Remove the advisory information for the source bucket Id.
        for advInfo in self._advMap[source]:
            name = dict(advInfo)['name']
            if name == advisory:
                self._advMap[source].remove(advInfo)
                if not len(self._advMap[source]):
                    del self._advMap[source]
                self._advMap.setdefault(dest, set()).add(advInfo)
                break

    def _reorderSource(self, source, dest, nevra):
        """
        Reschedule an individual srpm to another bucket.
        If destination bucket is None, simply remove srpm from source bucket.
        """

        if dest:
            log.info('rescheduling %s %s -> %s' % (nevra, source, dest))
        else:
            log.info('removing ignored %s from %s' % (nevra, source))

        # Remove specified source nevra from the source bucket
        bucketNevras = dict([ (x.getNevra(), x)
                              for x in self._order[source] ])
        # FIXME: the above line will fail with a KeyError exception in
        # cases where a removal directive refers to a bucket that
        # doesn't exist.  Add an option to prevent that and silently
        # ignore?  (PFM-806)
        if nevra not in bucketNevras:
            raise PackageNotFoundInBucketError(nevra=nevra, bucketId=source)
        srpm = bucketNevras[nevra]
        self._order[source].remove(srpm)
        if not len(self._order[source]):
            del self._order[source]

        # Remove all references to this srpm being part of an advisory
        for advisory in self._advPkgRevMap.pop(srpm, set()):
            self._advPkgMap[advisory].remove(srpm)
            if not len(self._advPkgMap[advisory]):
                del self._advPkgMap[advisory]

        if dest:
            # Move srpm to destination bucket if not a removal.
            self._order.setdefault(dest, set()).add(srpm)

    def _getNevra(self, pkg):
        """
        Get the NEVRA of a package object and do any transformation required.
        """

        # convert nevra to yum compatible nevra
        nevra = list(pkg.nevra.getNevra())
        if nevra[1] is None:
            nevra[1] = '0'
        if type(nevra[1]) == int:
            nevra[1] = str(nevra[1])
        nevra = tuple(nevra)

        return nevra

    @staticmethod
    def _mktime(date_str):
        """Convert a datetime string, assumed to be in the EST5EDT zone, to a
        POSIX timestamp.
        """
        # Shouldn't this be in datetime or something? It's pretty awful.
        ref_zone = dateutil_tz.gettz('EST5EDT')
        assert ref_zone is not None
        utc_zone = dateutil_tz.tzutc()
        epoch = datetime.datetime.fromtimestamp(0, utc_zone)
        as_local = dateutil_parser.parse(date_str).replace(tzinfo=ref_zone)
        as_utc = as_local.astimezone(utc_zone)
        offset = as_utc - epoch
        return ((offset.days * 60*60*24) +
                (offset.seconds) +
                (offset.microseconds * 1e-6))

    def _sortPackagesByErrataTimestamp(self):
        """
        Sort packages by errata release timestamp.
        """

        # get mapping of nevra to source pkg object
        sources = dict( ((x.name, x.epoch, x.version, x.release, x.arch), y)
                        for x, y in self._pkgSource.binPkgMap.iteritems() )

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
            log.info('processing %s' % e.advisory)

            # Get unique list of nevras for which we have packages indexed and
            # are of a supported arch.
            errataNevras = set([ self._getNevra(x) for x in e.nevraChannels
                                 if x.channel.label in indexedChannels and
                                    x.nevra.arch in arches ])

            for nevra in errataNevras:
                # add package to advisory package map
                self._advPkgMap.setdefault(e.advisory,
                                           set()).add(sources[nevra])
                self._advPkgRevMap.setdefault(sources[nevra],
                                              set()).add(e.advisory)

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
                if e.advisory in self._cfg.brokenErrata:
                    msg = log.warn
                else:
                    broken.append(e.advisory)
                    msg = log.critical
                msg('broken advisory: %s' % e.advisory)

            if bucketId is None:
                bucketId = int(self._mktime(e.issue_date))

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
        if self._cfg.firstErrata:
            firstErrata = self._cfg.firstErrata
        else:
            firstErrata = int(time.time())
            if len(buckets):
                firstErrata = sorted(buckets.keys())[0]
                
        for nevra, pkg in nevras.iteritems():
            buildtime = int(pkg.buildTimestamp)
            if buildtime < firstErrata:
                golden.append(pkg)
            else:
                other.append(pkg)

        buckets[0] = golden

        # Dump cached errata results once we are done with them.
        self._errata.cleanup()

        return buckets, other


class _ConaryHelperShim(conaryhelper.ConaryHelper):
    """
    Shim class that doesn't actually change the repository.
    """

    def __init__(self, cfg):
        conaryhelper.ConaryHelper.__init__(self, cfg)
        self._client = None
        # This doesn't work... leave uninitialized
        #self._findTrovesCache = FindTrovesCache(None)

    @staticmethod
    def _getCacheKey(nvf):
        n, v, f = nvf
        if v and hasattr(v, 'trailingRevision'):
            v = v.trailingRevision().getVersion()
        return (n, v)

    def populateFindTrovesCache(self, labels):
        """
        Pre populate the find troves cache with all versions from all labels
        listed.
        """

        req = { None: dict((x, None) for x in labels) }
        trvs = self._repos.getTroveVersionsByLabel(req)

        for n, vd in trvs.iteritems():
            for v, fs in vd.iteritems():
                key = self._getCacheKey((n, v, None))
                self._findTrovesCache[key] = [ (n, v, f) for f in fs ]

    def findTroves(self, troveList, labels=None, *args, **kwargs):
        """
        Aggresivly cache all findTroves queries as they are not likely to change
        while sanity checking.
        """

        if not labels:
            return []

        # Find any requests that are already cached.
        cached = set([ x for x in troveList
                       if self._getCacheKey(x) in self._findTrovesCache ])

        # Filter out cached requests.
        needed = set(troveList) - cached

        # Query for new requets.
        if needed:
            #log.critical('CACHE MISS')
            #log.critical('request: %s' % troveList)
            trvs = conaryhelper.ConaryHelper.findTroves(self, needed,
                labels=labels, *args, **kwargs)
        else:
            #log.info('CACHE HIT')
            trvs = {}

        # Cache new requests.
        self._findTrovesCache.update(dict([ (self._getCacheKey(x), y)
                for x, y in trvs.iteritems() ]))

        # Pull results out of the cache.
        res = dict([ (x, self._findTrovesCache.get(self._getCacheKey(x), []))
                     for x in troveList ])

        return res

    def getLatestSourceVersion(self, pkgname):
        """
        Stub for latest version.
        """

        return False

    def _not_implemented(self, *args, **kwargs):
        """
        Stub for methods that this class does not implemented.
        """
        raise NotImplementedError

    setTroveMetadata = _not_implemented
    mirror = _not_implemented
    promote = _not_implemented
    getSourceTroves = _not_implemented
    getSourceVersions = _not_implemented

    def _checkout(self, pkgname, version=None):
        """
        Checkout stub.
        """

        if version and not self.isOnBuildLabel(version):
            return conaryhelper.ConaryHelper._checkout(self, pkgname,
                                                       version=version)

        recipeDir = self._getRecipeDir(pkgname)
        return recipeDir

    _newpkg = _checkout

    @staticmethod
    def _addFile(pkgDir, fileName):
        """
        addFile stub.
        """

    _removeFile = _addFile

    def _commit(self, pkgDir, commitMessage):
        """
        commit stub.
        """

        log.info('committing %s' % os.path.basename(pkgDir))
