#
# Copyright (c) 2009-2010 rPath, Inc.
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

import os
import copy
import time
import logging

from updatebot import update
from updatebot import conaryhelper
from updatebot.errors import ErrataPackageNotFoundError
from updatebot.errors import ErrataSourceDataMissingError
from updatebot.errors import PackageNotFoundInBucketError
from updatebot.errors import AdvisoryPackageMissingFromBucketError

# update errors
from updatebot.errors import UpdateGoesBackwardsError
from updatebot.errors import UpdateRemovesPackageError
from updatebot.errors import UpdateReusesPackageError

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
    def getVersions(self, bucketId):
        """
        Get a set of group versions that should be built for the given bucketId.
        @param bucketId: identifier for a given update slice
        @type bucketId: integer (unix time)
        """

        versions = set()
        for advisory in sellf.getUpdateDetail(bucketId):
            versions.add(self._errata.getGroupVersion(advisory['name']))
        return versions

    def getBucketVersion(self, bucketId):
        """
        Convert a bucketId to a conary version.
        @param bucketId: identifier for a given update slice
        @type bucketId: integer (unix time)
        """

        version = time.strftime('%Y.%m.%d_%H%M.%S', time.gmtime(bucketId))
        return version

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
        updater = update.Updater(self._cfg, pkgSource)
        updater._conaryhelper = _ConaryHelperShim(self._cfg)

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
                log.warn('found duplicates in %s' % updateId)
                errors.setdefault(updateId, []).append(('duplicates', dups))

        # Play though entire update history to check for iregularities.
        current = {}
        removals = self._cfg.updateRemovesPackages
        replaces = self._cfg.updateReplacesPackages
        currentlyRemovedBinaryNevras = set()
        foundObsoleteEdges = set()
        foundObsoleteSrcs = set()
        for updateId in sorted(self._order.keys()):
            log.info('validating %s' % updateId)
            expectedRemovals = removals.get(updateId, [])
            expectedReplaces = replaces.get(updateId, [])
            explicitSourceRemovals = self._cfg.removeSource.get(updateId, set())
            explicitBinaryRemovals = self._cfg.removeObsoleted.get(updateId, set())

            assert len(self._order[updateId])
            for srpm in self._order[updateId]:
                nvf = (srpm.name, None, None)

                # validate updates
                try:
                    assert updater._sanitizeTrove(nvf, srpm,
                        expectedRemovals=expectedRemovals + expectedReplaces)
                except (UpdateGoesBackwardsError,
                        UpdateRemovesPackageError,
                        UpdateReusesPackageError), e:
                    errors.setdefault(updateId, []).append(e)

                # apply update to checkout
                if srpm.getNevra() in explicitSourceRemovals:
                    log.error('Removing %s in %s would cause it never to be promoted' %
                              (str(' '.join(srpm.getNevra())), updateId))
                current[srpm.name] = srpm
                assert not updater.update(nvf, srpm)

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
                        # we exclude any source only once, not per bucket
                        obsoleteSources.add(
                            (obsoletedPkg.name,
                             obsoletedPkg,
                             obsoletingSrcPkgs,
                             srcPkg,
                             binPkgs))
                        foundObsoleteSrcs.add(srcPkg)


            if obsoleteBinaries:
                log.warn('found obsolete binary packages in %s' % updateId)
                errors.setdefault(updateId, []).append(('obsoleteBinaries',
                                                        obsoleteBinaries))
            if obsoleteSources:
                log.warn('found obsolete source packages in %s' % updateId)
                errors.setdefault(updateId, []).append(('obsoleteSources',
                                                        obsoleteSources))
            if removedShouldBeReplaced:
                log.warn('found removals for replacements in %s' % updateId)
                errors.setdefault(updateId, []).append(('removedShouldBeReplaced',
                                                        removedShouldBeReplaced))

        # Report errors.
        for updateId, error in sorted(errors.iteritems()):
            for e in error:
                if isinstance(e, UpdateGoesBackwardsError):
                    one, two = e.why
                    oneNevra = str(' '.join(one.getNevra()))
                    twoNevra = str(' '.join(two.getNevra()))
                    log.warn('%s %s -revertsTo-> %s' % (updateId,
                             oneNevra, twoNevra))
                    log.info('%s -revertsTo-> %s' % (
                             rhnUrls(srpmToAdvisory[one]),
                             rhnUrls(srpmToAdvisory[two])))
                    log.info('%s %s (%d) -> %s (%d)' % (updateId,
                             tconv(srpmToBucketId[one]), srpmToBucketId[one],
                             tconv(srpmToBucketId[two]), srpmToBucketId[two]))
                    log.info('? reorderSource %s otherId<%s %s' % (
                        updateId, srpmToBucketId[one], twoNevra))
                    for errataId in srpmToAdvisory[two]:
                        log.info('? reorderAdvisory %s otherId<%s %s' % (
                            updateId, srpmToBucketId[one], errataId))
                elif isinstance(e, UpdateReusesPackageError):
                    # Note that updateObsoletesPackages not yet implemented...
                    log.warn('%s %s reused in %s; check for obsoletes?' % (
                             updateId, e.pkgNames, e.newspkg))
                    for name in sorted(set(p.name for p in e.pkgList)):
                        log.info('? updateObsoletesPackages %s %s' % (
                                 updateId, name))
                elif isinstance(e, UpdateRemovesPackageError):
                    log.warn('%s %s removed in %s' % (
                             updateId, e.pkgNames, e.newspkg))
                    for name in sorted(set(p.name for p in e.pkgList)):
                        log.info('? updateRemovesPackages %s %s' % (
                                 updateId, name))
                elif isinstance(e, tuple):
                    if e[0] == 'duplicates':
                        sortedOrder = sorted(self._order)
                        previousId = sortedOrder[sortedOrder.index(updateId)-1]
                        for dupName, dupSet in e[1].iteritems():
                            dupList = sorted(dupSet)
                            log.warn('%s contains duplicate %s %s' %(updateId,
                                dupName, dupList))
                            for srcPkg in dupList[:-1]:
                                srcNevra = str(' '.join(srcPkg.getNevra()))
                                log.info('%s : %s' % (
                                    srcNevra, rhnUrls(srpmToAdvisory[srcPkg])))
                                log.info('? reorderSource %s earlierId>%s %s' %
                                    (updateId, previousId, srcNevra))
                                for errataId in srpmToAdvisory[srcPkg]:
                                    log.info(
                                        '? reorderAdvisory %s earlierId>%s %r'
                                        % (updateId, previousId, errataId))

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
                                log.warn('%s %s obsoletes %s (%s)' % (
                                         updateId, obsoletingPkg,
                                         obsoletedPkg, obsoleteName))
                                log.info('? keepObsolete %s %s' %
                                         (obsoletingNevra, obsoletedNevra))
                                log.info('? removeObsoleted %s %s' % (updateId,
                                         obsoleteName))
                            log.warn('Not "removeSource %s"; that would remove non-obsoleted %s' %
                                     (srcNevraStr, unremovedStr))

                    elif e[0] == 'obsoleteSources':
                        for (obsoleteName, obsoletedPkg, obsoletingSrcPkgs,
                             srcPkg, binPkgs) in e[1]:
                            srcNevra = srcPkg.getNevra()
                            srcNevraStr = str(' '.join(srcNevra))
                            obsoletingSrcPkgNames = str(' '.join(sorted(set(
                                x.name for x in obsoletingSrcPkgs))))
                            pkgList = str(' '.join(repr(x) for x in binPkgs))
                            log.warn('%s %s obsolete(s) %s (%s)' % (
                                     updateId, obsoletingSrcPkgNames,
                                     obsoletedPkg, obsoleteName))
                            log.info('? removeSource %s %s # %s' % (
                                     updateId, srcNevraStr,
                                     obsoletingSrcPkgNames))
                            log.info(' will remove the following: %s' % pkgList)
                    elif e[0] == 'removedShouldBeReplaced':
                        for pkgName in e[1]:
                            log.warn('%s removed package %s should be replaced' % (
                                     updateId, pkgName))
                            log.info('? updateReplacesPackages %s %s' % (
                                     updateId, pkgName))


        # Fail if there are any errors.
        assert not errors

        log.info('order sanity checking complete')

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

        ##
        # Start order munging here
        ##

        # Make sure we don't drop any updates
        totalPkgs = sum([ len(x) for x in self._order.itervalues() ])
        pkgs = set()
        for pkgSet in self._order.itervalues():
            pkgs.update(pkgSet)
        assert len(pkgs) == totalPkgs

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

        # Make sure we don't drop any updates
        totalPkgs2 = sum([ len(x) for x in self._order.itervalues() ])
        pkgs = set()
        for pkgSet in self._order.itervalues():
            pkgs.update(pkgSet)
        assert len(pkgs) == totalPkgs2
        assert totalPkgs2 == totalPkgs

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

        # Warn when moving advisory into existing bucket.
        if dest in self._order:
            log.warn('inserting %s into pre-existing bucket' % advisory)

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
        """

        # Warn when moving srpm into existing bucket.
        if dest in self._order:
            log.warn('inserting %s into pre-existing bucket' % '-'.join(nevra))

        log.info('rescheduling %s %s -> %s' % (nevra, source, dest))

        # Remove specified source nevra from the source bucket
        bucketNevras = dict([ (x.getNevra(), x)
                              for x in self._order[source] ])
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

        # Move srpm to destination bucket
        self._order.setdefault(dest, set()).add(srpm)

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

                # add package to advisory package map
                self._advPkgMap.setdefault(e.advisory, set()).add(sources[nevra])
                self._advPkgRevMap.setdefault(sources[nevra], set()).add(e.advisory)

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


class _ConaryHelperShim(conaryhelper.ConaryHelper):
    """
    Shim class that doesn't actually change the repository.
    """

    def __init__(self, cfg):
        conaryhelper.ConaryHelper.__init__(self, cfg)
        self._client = None
        self._repos = None

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

    def _checkout(self, pkgname):
        """
        Checkout stub.
        """

        #log.info('checking out %s' % pkgname)

        recipeDir = self._getRecipeDir(pkgname)
        return recipeDir

    _newpkg = _checkout

    @staticmethod
    def _addFile(pkgDir, fileName):
        """
        addFile stub.
        """

        #log.info('adding file %s' % fileName)

    _removeFile = _addFile

    def _commit(self, pkgDir, commitMessage):
        """
        commit stub.
        """

        log.info('committing %s' % os.path.basename(pkgDir))
