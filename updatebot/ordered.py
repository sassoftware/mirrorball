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
Module for doing updates ordered by errata information.
"""

import time
import pickle
import logging
import tempfile
import itertools

from conary import versions
from conary.deps import deps

from updatebot import errata
from updatebot import groupmgr
from updatebot.lib import watchdog
from updatebot.bot import Bot as BotSuperClass

from updatebot.errors import SourceNotImportedError
from updatebot.errors import UnknownRemoveSourceError
from updatebot.errors import PlatformNotImportedError
from updatebot.errors import TargetVersionNotFoundError
from updatebot.errors import PromoteMissingVersionError
from updatebot.errors import PromoteFlavorMismatchError
from updatebot.errors import PlatformAlreadyImportedError
from updatebot.errors import FoundModifiedNotImportedErrataError

log = logging.getLogger('updatebot.ordered')

class Bot(BotSuperClass):
    """
    Implement errata driven create/update interface.
    """

    _create = BotSuperClass.create
    _update = BotSuperClass.update

    def __init__(self, cfg, errataSource):
        BotSuperClass.__init__(self, cfg)
        self._errata = errata.ErrataFilter(self._cfg, self._pkgSource,
            errataSource)
        self._groupmgr = groupmgr.GroupManager(self._cfg,
            useMap=self._pkgSource.useMap)

        if self._cfg.platformSearchPath:
            self._parentGroup = groupmgr.GroupManager(self._cfg,
                                                      parentGroup=True)

    def _addPackages(self, pkgMap, group):
        """
        Add pkgMap to group.
        """

        for binSet in pkgMap.itervalues():
            pkgs = {}
            for n, v, f in binSet:
                if ':' in n:
                    continue
                elif n not in pkgs:
                    pkgs[n] = {v: set([f, ])}
                elif v not in pkgs[n]:
                    pkgs[n][v] = set([f, ])
                else:
                    pkgs[n][v].add(f)

            for name, vf in pkgs.iteritems():
                assert len(vf) == 1
                version = vf.keys()[0]
                flavors = list(vf[version])
                log.info('adding %s=%s' % (name, version))
                for f in flavors:
                    log.info('\t%s' % f)
                group.addPackage(name, version, flavors)

    def _modifyGroups(self, updateId, group):
        """
        Apply the list of modifications, if available, from the config to the
        group model.
        """

        addPackages = self._cfg.addPackage.get(updateId, None)
        removePackages = self._cfg.removePackage.get(updateId, None)

        # Don't taint group model unless something has actually changed.
        if addPackages or removePackages:
            group.modifyContents(additions=addPackages, removals=removePackages)

    def _savePackages(self, pkgMap, fn=None):
        """
        Save the package map to a file.
        """

        if fn is None:
            fn = tempfile.mktemp()

        log.info('saving package map to file: %s' % fn)

        # freeze contents
        frzPkgs = dict([ ((x[0], x[1].freeze(), x[2]),
                          set([ (z[0], z[1].freeze(), z[2].freeze())
                                for z in y]))
                          for x, y in pkgMap.iteritems() ])

        # pickle frozen contents
        pickle.dump(frzPkgs, open(fn, 'w'))

    def _restorePackages(self, fn):
        """
        Restore the frozen form of the package map.
        """

        log.info('restoring package map from file: %s' % fn)

        thawVersion = versions.ThawVersion

        def thawFlavor(flv):
            if flv is None:
                return flv
            else:
                return deps.ThawFlavor(flv)

        # load pickle
        frzPkgs = pickle.load(open(fn))

        # thaw versions and flavors
        pkgMap = dict([ ((x[0], thawVersion(x[1]), thawFlavor(x[2])),
                         set([ (z[0], thawVersion(z[1]), thawFlavor(z[2]))
                               for z in y ]))
                        for x, y in frzPkgs.iteritems() ])

        return pkgMap

    def create(self, *args, **kwargs):
        """
        Handle initial import case.
        """

        group = self._groupmgr.getGroup()

        # Make sure this platform has not already been imported.
        if group.errataState is not None:
            raise PlatformAlreadyImportedError

        self._pkgSource.load()
        toCreate = self._errata.getInitialPackages()

        fltr = kwargs.pop('fltr', None)
        if fltr:
            toCreate = fltr(toCreate)

        pkgMap, failures = self._create(*args, toCreate=toCreate, **kwargs)

        # Insert package map into group.
        self._addPackages(pkgMap, group)

        # Save group changes if there are any failures.
        if failures:
            self._groupmgr.setGroup(group)

        # Try to build the group if everything imported.
        else:
            self._modifyContents(0, group)
            group.errataState = '0'
            group.version = '0'
            group = group.commit()
            group.build()

        return pkgMap, failures

    def update(self, *args, **kwargs):
        """
        Handle update case.
        """

        # Load specific kwargs
        restoreFile = kwargs.pop('restoreFile', None)

        # Get current group
        group = self._groupmgr.getGroup()

        # Get current timestamp
        current = group.errataState
        if current is None:
            raise PlatformNotImportedError

        # Check to see if there is a binary version if the current group.
        # This handles restarts where the group failed to build, but we don't
        # want to rebuild all of the packages again.
        if not group.hasBinaryVersion():
            group.build()

        # Load package source.
        self._pkgSource.load()

        # Sanity check errata ordering.
        self._errata.sanityCheckOrder()

        # Check for updated errata that may require some manual changes to the
        # repository. These are errata that were issued before the current
        # errata state, but have been modified in the upstream errata source.
        changed = self._errata.getModifiedErrata(current)
        # Iterate through changed and verify the current conary repository
        # contents against any changes.
        if changed:
            notimported = set()
            expectedDowngrades = [ x for x in
                itertools.chain(*self._cfg.allowPackageDowngrades.values()) ]
            sourceExceptions = dict((x[2], x[1])
                for x in self._cfg.reorderAdvisory)
            log.info('found modified updates, validating repository state')
            for advisory, advInfo in changed.iteritems():
                log.info('validating %s' % advisory)
                for srpm in advInfo['srpms']:
                    log.info('checking %s' % srpm.name)
                    # This will raise an exception if any inconsistencies are
                    # detected.
                    try:
                        self._updater.sanityCheckSource(srpm,
                            allowPackageDowngrades=expectedDowngrades)
                    except SourceNotImportedError, e:
                        if (advisory in sourceExceptions and
                            sourceExceptions[advisory] > current):
                            log.info('found exception for advisory')
                            continue
                        notimported.add(advisory)

            if notimported:
                raise FoundModifiedNotImportedErrataError(
                    advisories=notimported)

        log.info('starting update run')

        count = 0
        startime = time.time()
        updateSet = {}
        for updateId, updates in self._errata.iterByIssueDate(current=current):
            start = time.time()
            detail = self._errata.getUpdateDetailMessage(updateId)
            log.info('attempting to apply %s' % detail)

            # If on a derived platform and the current updateId is greater than
            # the parent updateId, stop applying updates.
            if self._cfg.platformSearchPath:
                # FIXME: This means that if there is an update the the child
                #        platform that is not included in the parent platform,
                #        we will not apply the update until there is a later
                #        update to the parent platform.
                parentState = self._parentGroup.getErrataState()
                if parentState < updateId:
                    log.info('reached end of parent platform update stream')
                    continue

            # remove packages from config
            removePackages = self._cfg.updateRemovesPackages.get(updateId, [])
            removeObsoleted = self._cfg.removeObsoleted.get(updateId, [])
            removeReplaced = self._cfg.updateReplacesPackages.get(updateId, [])

            # take the union of the three lists to get a unique list of packages
            # to remove.
            expectedRemovals = (set(removePackages) |
                                set(removeObsoleted) |
                                set(removeReplaced))
            # The following packages are expected to exist and must be removed
            # (removeObsoleted may be mentioned for buckets where the package
            # is not in the model, in order to support later adding the ability
            # for a package to re-appear if an RPM obsoletes entry disappears.)
            requiredRemovals = (set(removePackages) |
                                set(removeReplaced))

            # Get the list of package that are allowed to be downgraded.
            allowDowngrades = self._cfg.allowPackageDowngrades.get(updateId, [])

            # If recovering from a failure, restore the pkgMap from disk.
            if restoreFile:
                pkgMap = self._restorePackages(restoreFile)
                restoreFile = None

            # Update package set.
            else:
                fltr = kwargs.pop('fltr', None)
                if fltr:
                    updates = fltr(updates)

                pkgMap = self._update(*args, updatePkgs=updates,
                    expectedRemovals=expectedRemovals,
                    allowPackageDowngrades=allowDowngrades, **kwargs)

            # When deriving from an upstream platform sometimes we don't want
            # the latest versions.
            oldVersions = self._cfg.useOldVersion.get(updateId, None)
            if self._cfg.platformSearchPath and oldVersions:
                for nvf in oldVersions:
                    # Lookup all source and binaries that match this binary.
                    srcMap = self._updater.getSourceVersionMapFromBinaryVersion(
                        nvf, labels=self._cfg.platformSearchPath, latest=False)

                    # Make sure there is only one
                    assert len(srcMap) == 1

                    # Filter out any versions that don't match the version we
                    # are looking for.
                    curVerMap = dict((x, [ z for z in y
                                           if z[1].asString() == nvf[1] ])
                                     for x, y in srcMap.iteritems())

                    # Make sure the version we are looking for is in the list
                    assert curVerMap and curVerMap.values()[0]

                    # Update the package map with the new versions.
                    pkgMap.update(curVerMap)

            # Save package map in case we run into trouble later.
            self._savePackages(pkgMap)

            # Store current updateId.
            group.errataState = updateId

            # Remove any packages that are scheduled for removal.
            # NOTE: This should always be done before adding packages so that
            #       any packages that move between sources will be removed and
            #       then readded.
            if requiredRemovals:
                log.info('removing the following packages from the managed '
                    'group: %s' % ', '.join(requiredRemovals))
                for pkg in requiredRemovals:
                    group.removePackage(pkg)
            if removeObsoleted:
                log.info('removing any of obsoleted packages from the managed '
                    'group: %s' % ', '.join(removeObsoleted))
                for pkg in removeObsoleted:
                    group.removePackage(pkg, missingOk=True)

            # Handle the case of entire source being obsoleted, this causes all
            # binaries from that source to be removed from the group model.
            if updateId in self._cfg.removeSource:
                # get nevras from the config
                nevras = self._cfg.removeSource[updateId]

                # get a map of source nevra to binary package list.
                nevraMap = dict((x.getNevra(), y) for x, y in
                                self._pkgSource.srcPkgMap.iteritems()
                                if x.getNevra() in nevras)

                for nevra in nevras:
                    # if for some reason the nevra from the config is not in
                    # the pkgSource, raise an error.
                    if nevra not in nevraMap:
                        raise UnknownRemoveSourceError(nevra=nevra)

                    # remove all binary names from the group.
                    binNames = set([ x.name for x in nevraMap[nevra] ])
                    for name in binNames:
                        group.removePackage(name)

            # Make sure built troves are part of the group.
            self._addPackages(pkgMap, group)

            # Modify any extra groups to match config.
            self._modifyGroups(updateId, group)

            # Get timestamp version.
            version = self._errata.getBucketVersion(updateId)
            if not version:
                version = 'unknown.%s' % updateId

            # Build groups.
            log.info('setting version %s' % version)
            group.version = version

            group = group.commit()
            grpTrvMap = group.build()

            updateSet.update(pkgMap)

            # Report timings
            advTime = time.strftime('%m-%d-%Y %H:%M:%S',
                                    time.localtime(updateId))
            totalTime = time.time() - start
            log.info('published update %s in %s seconds' % (advTime, totalTime))
            count += 1

        log.info('update completed')
        log.info('applied %s updates in %s seconds'
            % (count, time.time() - startime))

        return updateSet

    def promote(self):
        """
        Promote binary groups from the devel label to the production lable in
        the order that they were built.
        """

        # Get current timestamp
        current = self._groupmgr.latest.errataState
        if current is None:
            raise PlatformNotImportedError

        # laod package source
        self._pkgSource.load()

        log.info('querying repository for all group versions')
        sourceLatest = self._updater.getUpstreamVersionMap(self._cfg.topGroup)

        log.info('querying target label for all group versions')
        targetLatest = self._updater.getUpstreamVersionMap(
            (self._cfg.topGroup[0], self._cfg.targetLabel, None))

        log.info('starting promote')

        count = 0
        startime = time.time()

        # Get all updates after the first bucket.
        missing = False
        for updateId, bucket in self._errata.iterByIssueDate(current=1):
            upver = self._errata.getBucketVersion(updateId)

            # Don't try to promote buckets that have already been promoted.
            if upver in targetLatest:
                log.info('%s found on target label, skipping' % upver)
                continue

            # Make sure version has been imported.
            if upver not in sourceLatest:
                missing = upver
                continue

            # If we find a missing version and then find a version in the
            # repository report an error.
            if missing:
                log.critical('found missing version %s' % missing)
                raise PromoteMissingVersionError(missing=missing, next=upver)

            log.info('starting promote of %s' % upver)

            # Get conary versions to promote
            toPromote = sourceLatest[upver]

            # Make sure we have the expected number of flavors
            if len(set(x[2] for x in toPromote)) != len(self._cfg.groupFlavors):
                log.error('did not find expected number of flavors')
                raise PromoteFlavorMismatchError(
                    cfgFlavors=self._cfg.groupFlavors, troves=toPromote,
                    version=toPromote[0][1])

            # Find excepted promote packages.
            srcPkgMap = self._updater.getBinaryVersionsFromSourcePackages(
                bucket)
            exceptions = dict([ (x[0], x[1]) for x in itertools.chain(
                *self._getOldVersionExceptions(updateId).itervalues()) ])

            # These are the binary trove specs that we expect to be promoted.
            expected = self._filterBinPkgSet(
                itertools.chain(*srcPkgMap.itervalues()), exceptions)

            # Get list of extra troves from the config
            extra = self._cfg.extraExpectedPromoteTroves.get(updateId, [])

            def promote():
                # Create and validate promote changeset
                packageList = self._updater.publish(toPromote, expected,
                    self._cfg.targetLabel, extraExpectedPromoteTroves=extra)
                return 0

            rc = watchdog.waitOnce(promote)
            if rc:
                break
            count += 1

        log.info('promote complete')
        log.info('promoted %s groups in %s seconds'
            % (count, time.time() - startime))

    def createErrataGroups(self):
        """
        Create groups for each advisory that only contain the versions of
        packages that were included in that advisory. Once created, promote
        to production branch.
        """

        # Get current timestamp
        current = self._groupmgr.latest.errataState
        if current is None:
            raise PlatformNotImportedError

        # Load package source.
        self._pkgSource.load()

        # Get latest errataState from the targetLabel so that we can fence group
        # building based on the target label state.
        targetGroup = groupmgr.GroupManager(self._cfg, targetGroup=True)
        targetErrataState = targetGroup.latest.errataState

        log.info('starting errata group processing')

        count = 0
        startime = time.time()

        for updateId, updates in self._errata.iterByIssueDate(current=0):
            # Stop if the updateId is greater than the state of the latest group
            # on the production label.
            if updateId > targetErrataState:
                log.info('current updateId (%s) is newer than target label '
                    'contents' % updateId)
                break

            # Make sure the group representing the current updateId has been
            # imorted and promoted to the production label.
            version = self._errata.getBucketVersion(updateId)
            if not targetGroup.hasBinaryVersion(sourceVersion=version):
                raise TargetVersionNotFoundError(version=version,
                                                 updateId=updateId)

            # Lookup any places we need to use old versions ahead of time.
            multiVersionExceptions = dict([
                (x[0], x[1]) for x in itertools.chain(
                    self._updater.getTargetVersions(itertools.chain(
                *self._getOldVersionExceptions(updateId).itervalues()
                    ))[0]
                )
            ])

            # Now that we know that the packages that are part of this update
            # should be on the target label we can separate things into
            # advisories.
            mgr = groupmgr.ErrataGroupManagerSet(self._cfg)
            groupNames = self._errata.getNames(updateId)
            for advInfo in self._errata.getUpdateDetail(updateId):
                advisory = advInfo['name']
                log.info('%s: processing' % advisory)

                srcPkgs = self._errata.getAdvisoryPackages(advisory)
                assert srcPkgs

                targetGrp = groupmgr.SingleGroupManager(groupNames[advisory],
                    self._cfg, targetGroup=True)

                if targetGrp.hasBinaryVersion():
                    log.info('%s: found existing version, skipping' % advisory)
                    continue

                grp = mgr.newGroup(groupNames[advisory]).getGroup()
                grp.version = version
                grp.errataState = updateId

                log.info('%s: finding built packages' % advisory)
                binTrvMap = \
                    self._updater.getBinaryVersionsFromSourcePackages(srcPkgs)

                binTrvs = set()
                for srcPkg, binTrvSpecs in binTrvMap.iteritems():
                    targetSpecs, failed = self._updater.getTargetVersions(
                        binTrvSpecs)
                    binTrvs.update(set(targetSpecs))

                # Handle attaching an update that was caused by changes that we
                # made outside of the normal update stream to an existing
                # advisory.
                for nvf in self._cfg.extendAdvisory.get(advisory, ()):
                    srcMap = self._updater.getSourceVersionMapFromBinaryVersion(
                        nvf, labels=self._cfg.platformSearchPath,
                        latest=False, includeBuildLabel=True)
                    assert len(srcMap) == 1
                    targetVersions = self._updater.getTargetVersions(
                        srcMap.values()[0])[0]
                    binTrvs.update(set(targetVersions))

                # Group unique versions by flavor
                nvfMap = {}
                for n, v, f in self._filterBinPkgSet(binTrvs, multiVersionExceptions):
                    n = n.split(':')[0]
                    nvfMap.setdefault((n, v), set()).add(f)

                # Add packages to group model.
                for (n, v), flvs in nvfMap.iteritems():
                    log.info('%s: adding package %s=%s' % (advisory, n, v))
                    for f in flvs:
                        log.info('%s: %s' % (advisory, f))
                    grp.addPackage(n, v, flvs)

            # Make sure there are groups to build.
            if not mgr.hasGroups():
                log.info('%s: groups already built and promoted' % updateId)
                continue

            log.info('%s: building groups' % updateId)
            trvMap = mgr.build()

            log.info('%s: promoting groups' % updateId)
            # Setting expected to an empty tuple since we don't expect anything
            # other than groups to be promoted.
            expected = tuple()
            toPromote = self._flattenSetDict(trvMap)
            promoted = self._updater.publish(toPromote, expected,
                                             self._cfg.targetLabel)

            count += 1

        log.info('completed errata group processing')
        log.info('processed %s errata groups in %s seconds'
            % (count, time.time() - startime))

    def _getOldVersionExceptions(self, updateId):
        versionExceptions = {}
        if updateId in self._cfg.useOldVersion:
            log.info('looking up old version exception information')
            for oldVersion in self._cfg.useOldVersion[updateId]:
                srcMap = self._updater.getSourceVersionMapFromBinaryVersion(
                    oldVersion, labels=self._cfg.platformSearchPath,
                    latest=False, includeBuildLabel=True)
                versionExceptions.update(srcMap)

        return versionExceptions

    def _filterBinPkgSet(self, binSet, exceptions):
        binPkgs = {}
        for n, v, f in binSet:
            binPkgs.setdefault(n, dict()).setdefault(v, set()).add(f)

        uniqueSet = set()
        for n, vMap in binPkgs.iteritems():
            # Handle the case where a package has been rebuilt for some
            # reason, but we need to use the old version of the package.
            pkgName = n.split(':')[0]
            if len(vMap) > 1:
                if pkgName in exceptions:
                    log.info('using old version of %s' % n)
                    vMap = dict((x, y) for x, y in vMap.iteritems()
                                if x == exceptions[pkgName])
                else:
                    log.info('found multiple versions of %s, using latest' % n)
                    v = sorted(vMap)[-1]
                    vMap = { v: vMap[v], }

            assert len(vMap) == 1

            for v, flvs in vMap.iteritems():
                uniqueSet.update(set((n, v, f) for f in flvs))

        return uniqueSet
