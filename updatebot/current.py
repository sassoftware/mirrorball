#
# Copyright (c) 2009-2011 rPath, Inc.
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
Module for doing updates by importing all of the available packages and then
building groups of the latest versions by nevra.
"""

import time
import logging
import itertools

from conary.trovetup import TroveTuple
from conary.deps.deps import ThawFlavor

from rpmutils import NEVRA

from updatebot import groupmgr
from updatebot.bot import Bot as BotSuperClass

from updatebot.errors import UnknownRemoveSourceError
from updatebot.errors import PlatformNotImportedError
from updatebot.errors import PlatformAlreadyImportedError

log = logging.getLogger('updatebot.current')

class UpdateSet(object):
    """
    Basic structure for iterating over a set of update packages.
    """

    def __init__(self, updatePkgs):
        self._updatePkgs = updatePkgs

    def __len__(self):
        return len(self._updatePkgs)

    def __iter__(self):
        """
        Update pacakges in NEVRA order if we can.
        """

        data = {}
        for srcPkg in self._updatePkgs:
            data.setdefault(srcPkg.name, set()).add(srcPkg)

        while data:
            job = []
            toRemove = []
            for n, nevras in data.iteritems():
                nevra = sorted(nevras)[0]
                nevras.remove(nevra)
                job.append(nevra)

                if not nevras:
                    toRemove.append(n)

            for n in toRemove:
                data.pop(n)

            yield job

    def filterPkgs(self, fltr):
        if not fltr:
            return
        self._updatePkgs = fltr(self._updatePkgs)

    def pop(self):
        return self._updatePkgs.pop()


class Bot(BotSuperClass):
    """
    Implement package driven create/update interface.
    """

    _updateMode = 'current'

    _create = BotSuperClass.create
    _update = BotSuperClass.update

    def __init__(self, cfg):
        BotSuperClass.__init__(self, cfg)

        self._groupmgr = groupmgr.GroupManager(self._cfg, self._ui,
            useMap=self._pkgSource.useMap)

        if self._cfg.platformSearchPath:
            self._parentGroup = groupmgr.GroupManager(self._cfg, self._ui,
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

    def create(self, *args, **kwargs):
        """
        Handle initial import case.
        """

        raise NotImplementedError

        group = self._groupmgr.getGroup()
        if group.errataState == 'None':
            group.errataState = None

        # Make sure this platform has not already been imported.
        if group.errataState is not None:
            raise PlatformAlreadyImportedError

        self._pkgSource.load()

        # FIXME: Need to determine the initial set of packages to import. Maybe
        #        we find the first time every nevra appears or maybe we just
        #        import all of the packages we can see and build a latest group?
        toCreate = set()

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
            self._modifyGroups(0, group)
            group.errataState = '0'
            group.version = '0'
            group = group.commit()
            group.build()

        return pkgMap, failures

    def _removeSource(self, updateId, group):
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

        return group 

    def _useOldVersions(self, updateId, pkgMap):
        # When deriving from an upstream platform sometimes we don't want
        # the latest versions.
        #oldVersions = self._cfg.useOldVersion.get(updateId, None)
        # Since we want this to expire in the new mode useOldVersion timestamp 
        # Should be in the future. This way an old version will not remain 
        # pinned forever. If group breaks move the useOldVersion into the 
        # future (not far as that would defeat the purpose)    
        oldVersions = [ x for x in self._cfg.useOldVersion if x > updateId ]

        # FOR TESTING WE SHOULD INSPECT THE PKGMAP HERE
        #print "REMOVE LINE AFTER TESTING"
        #import epdb; epdb.st()

        #oldVersions = self._cfg.useOldVersion.get(updateId, None)
        if oldVersions:
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

        return pkgMap

    def _getNevrasForLabel(self, label):
        """
        Get a mapping of pkg nvf -> nevra for a given label. Use this method
        instead of the conary helper directly so that we are using NEVRA objects
        and already map epochs of None to 0 to match yum metadata.
        """

        nevraMap = self._updater._conaryhelper.getNevrasForLabel(label)

        newMap = {}
        for nvf, nevra in nevraMap.iteritems():
            # Skip nvfs that don't have a nevra
            if not nevra:
                continue

            # Skip sources.
            if nvf[1].isSourceVersion():
                continue

            # Repack nevra subbing '0' for '', since yum metadata doesn't
            # represent epochs of None.
            if nevra[1] == '':
                nevra = (nevra[0], '0', nevra[2], nevra[3], nevra[4])

            pkgNvf = (nvf[0].split(':')[0], nvf[1], nvf[2])
            newMap[pkgNvf] = NEVRA(*nevra)

        return newMap

    def _getLatestNevraPackageMap(self, nevraMap):
        """
        Take a mapping of nvf to nevra and transform it into nevra to latest
        package nvf.
        """

        nevras = {}
        for nvf, nevra in nevraMap.iteritems():
            nevras.setdefault(nevra, set()).add(nvf)

        ret = {}
        for nevra, pkgs in nevras.iteritems():
            ret[nevra] = sorted(pkgs)[-1]

        return ret

    def _getPromotePackages(self):
        """
        Get the packages that have beeen built on the buildLabel, but have yet
        to be promoted to the target label. You should only run accross these if
        the promote step in the package build failed.
        """

        helper = self._updater._conaryhelper

        # Get all of the nevras for the target and source labels.
        log.info('querying target nevras')
        targetNevras = self._getNevrasForLabel(self._cfg.targetLabel)
        log.info('querying source nevras')
        sourceNevras = self._getNevrasForLabel(helper._ccfg.buildLabel)

        # Massage nevra maps into nevra -> latest package nvf
        log.info('building latest nevra maps')
        targetLatest = self._getLatestNevraPackageMap(targetNevras)
        sourceLatest = self._getLatestNevraPackageMap(sourceNevras)

        # Now we need to map the target nvfs back the source nvfs they were
        # cloned from.
        log.info('querying target cloned from information')
        targetClonedFrom = helper.getClonedFromForLabel(self._cfg.targetLabel)

        # Now diff the two maps. We are looking for things that have been
        # updated on the source label, that have not made it to the target
        # label.
        toPromote = set()
        for nevra, nvf in sourceLatest.iteritems():
            # nevra has not been promoted.
            if nevra not in targetLatest:
                toPromote.add(nvf)
            # the conary package containing this nevra has been rebuilt.
            elif nvf not in targetClonedFrom:
                toPromote.add(nvf)

        return toPromote

    def _getUpdatePackages(self):
        """
        Compare the upstream yum repository and the conary repository to figure
        out what sources need to be updated.
        """

        log.info('finding updates')

        # Get a mapping of nvf -> nevra
        sourceNevras = self._getNevrasForLabel(
            self._updater._conaryhelper._ccfg.buildLabel)

        # Reverse the map and filter out old conary versions.
        sourceLatest = self._getLatestNevraPackageMap(sourceNevras)

        # Iterate over all of the available source rpms to find any versions
        # that have not been imported into the conary repository.
        toUpdate = set()
        toUpdateMap = {}
        for binPkg, srcPkg in self._pkgSource.binPkgMap.iteritems():
            # Skip over source packages
            if binPkg.arch == 'src':
                continue

            if binPkg.getNevra() not in sourceLatest:
                toUpdateMap.setdefault(srcPkg, set()).add(binPkg)
                toUpdate.add(srcPkg)

        return UpdateSet(toUpdate)

    def _getPreviousNVFForSrcPkg(self, srcPkg):
        """
        Figure out what this source package was meant to update.
        """

        # FIXME: Should make this take a list of srcPkgs so that we can
        #        avoid multiple repository calls.

        # Get a mapping of nvf -> nevra
        sourceNevras = self._getNevrasForLabel(
            self._updater._conaryhelper._ccfg.buildLabel)

        # Reverse the map and filter out old conary versions.
        sourceLatest = self._getLatestNevraPackageMap(sourceNevras)

        # Find the previous nevra
        srcPkgs = sorted(self._pkgSource.srcNameMap.get(srcPkg.name))
        idx = srcPkgs.index(srcPkg) - 1

        while idx >= 0:
            binPkgs = [ x for x in self._pkgSource.srcPkgMap[srcPkgs[idx]]
                if x.arch != 'src' ]

            # Apparently we have managed to not import (or maybe just build)
            # some sub packages, so let's iterate over all of them until we find
            # one that matches.
            for binPkg in binPkgs:
                if binPkg.getNevra() not in sourceLatest:
                    continue

                binNVF = sourceLatest[binPkg.getNevra()]
                sourceVersions = self._updater._conaryhelper.getSourceVersions(
                    [binNVF, ]).keys()

                assert len(sourceVersions) == 1
                return sourceVersions[0]

            # Apparently we managed to skip importing a source package, or maybe
            # it just didn't get built. Fall back to the previous source.
            idx -= 1

        # This is a new package
        if idx < 0:
            return (srcPkg.name, None, None)

        assert False, 'How did we get here?'

    def update(self, *args, **kwargs):
        """
        Handle update case.
        """

        # We don't use these for anything in current update mode, but need to
        # pop them off the kwargs dict so as to not confuse the lower level
        # update code.
        kwargs.pop('checkMissingPackages', None)
        kwargs.pop('restoreFile', None)

        # Get current group
        group = self._groupmgr.getGroup()

        # Get current timestamp
        current = group.errataState
        if current is None:
            raise PlatformNotImportedError

        # Get the latest errata state, increment if the source has been built.
        if group.hasBinaryVersion():
            group.errataState += 1
        updateId = group.errataState

        # Load package source.
        self._pkgSource.load()

        log.info('starting update run')

        starttime = time.time()

        # Figure out what packages still need to be promoted.
        promotePkgs = self._getPromotePackages()

        # Go ahead and promote any packages that didn't get promoted during the
        # last run or have been rebuilt since then.
        log.info('found %s packages that need to be promoted' %
            len(promotePkgs))
        self._updater.publish(promotePkgs, promotePkgs, self._cfg.targetLabel)

        # Figure out what packages need to be updated.
        updatePkgs = self._getUpdatePackages()

        # remove packages from config
        removePackages = self._cfg.updateRemovesPackages.get(updateId, [])
        removeObsoleted = self._cfg.removeObsoleted.get(updateId, [])
        removeReplaced = self._cfg.updateReplacesPackages.get(updateId, [])

        # take the union of the three lists to get a unique list of packages
        # to remove.
        expectedRemovals = (set(removePackages) |
                            set(removeObsoleted) |
                            set(removeReplaced))

        # Packages that would otherwise be removed
        keepRemoved = self._cfg.keepRemoved.get(updateId, [])

        # Update package set.
        pkgMap = {}
        if updatePkgs:
            updatePkgs.filterPkgs(kwargs.pop('fltr', None))

            for updateSet in updatePkgs:
                log.info('building set of update troves')
                updateTroves = set([ (self._getPreviousNVFForSrcPkg(x), x)
                    for x in updateSet])

                log.info('running update')

                pkgMap.update(self._update(*args, updateTroves=updateTroves,
                    updatePkgs=True, expectedRemovals=expectedRemovals,
                    keepRemovedPackages=keepRemoved,
                    **kwargs))

                # The NEVRA maps will be changing every time through. Make sure
                # the clear the cache.
                log.info('dumping conaryhelper cache')
                self._updater._conaryhelper.clearCache()

        log.info('completed package update of %s packages in %s seconds'
            % (len(updatePkgs), time.time()-starttime))

        return pkgMap

    def _addNewPackages(self, group):
        """
        Find all of the packages from the buildLabel that are newer that those
        in the group. Handle any obsoletes along the way.
        """

        # FIXME: Right now we are going to deal with the buildLabel, we probably
        #        want to switch to the target label once a script has been
        #        written to rewrite existing group models to map them onto
        #        target label versions.

        # Make sure nothing is cached before we get started.
        self._updater._conaryhelper.clearCache()

        # Get a mapping of nvf -> nevra
        nevraMap = self._getNevrasForLabel(
             self._updater._conaryhelper._ccfg.buildLabel)

        # Reverse the map and filter out old conary versions.
        latest = self._getLatestNevraPackageMap(nevraMap)

        # index by name, will need this later
        names = {}
        for nevra, nvf in latest.iteritems():
            names.setdefault(nevra[0], dict())[nevra] = nvf

        toAdd = {}
        toRemove = set()
        for pkg in group.iterpackages():
            flavor = ThawFlavor(str(pkg.flavor))
            nvf = TroveTuple(pkg.name, pkg.version, flavor)

            # Older groups contain packages that do not reference any
            # capsules. This was a side affect of how groups are managed in
            # ordered mode. Since we don't need to do that anymore, just
            # remove the package. Hopefully they won't creep back in.
            if nvf not in nevraMap:
                toRemove.add(nvf)
                continue

            assert nvf in nevraMap

            # Get the current nevra
            nevra = nevraMap[nvf]

            # Now we need to find all versions of this package that
            # are equal to or newer than the current nevra.
            pkgs = names.get(nevra.name)
            nevras = sorted(pkgs)
            idx = nevras.index(nevra)

            updates = {}
            while idx < len(nevras):
                updates[nevras[idx]] = pkgs[nevras[idx]]
                idx += 1

            ##
            # FIXME: Obsolete handling goes here
            #
            # For each new version figure out if there are any obsoletes that
            # need to be handled, then handle them.
            ##

            foo = updates[sorted(updates)[-1]]
            # If the only available package is the one that is already in the
            # group, skip it and move on.
            if foo == nvf:
                continue

            # For now just pick the latest one and add it to the group.
            toAdd.setdefault((foo[0], foo[1]), set()).add(foo[2])

        for nvf in toRemove:
            group.removePackage(nvf.name, flavor=nvf.flavor)

        for (name, version), flavors in toAdd.iteritems():
            group.addPackage(name, version, flavors)

    def buildgroups(self):
        """
        Find the latest packages on the production label by nevra and build a
        group, taking into account any packages that would have been obsoleted
        along the way.
        """

        starttime = time.time()

        # Load the pkg src
        self._pkgSource.load()

        # Get current group
        group = self._groupmgr.getGroup()

        # Get current timestamp
        current = group.errataState
        if current is None:
            raise PlatformNotImportedError

        # Get the latest errata state, increment if the source has been built.
        if group.hasBinaryVersion():
            group.errataState += 1
        updateId = group.errataState

        # remove packages from config
        removePackages = self._cfg.updateRemovesPackages.get(updateId, [])
        removeObsoleted = self._cfg.removeObsoleted.get(updateId, [])
        removeReplaced = self._cfg.updateReplacesPackages.get(updateId, [])

        # The following packages are expected to exist and must be removed
        # (removeObsoleted may be mentioned for buckets where the package
        # is not in the model, in order to support later adding the ability
        # for a package to re-appear if an RPM obsoletes entry disappears.)
        requiredRemovals = (set(removePackages) |
                            set(removeReplaced))

        # Get the list of package that are allowed to be downgraded.
        allowDowngrades = self._cfg.allowPackageDowngrades.get(updateId, [])

        # Keep Obsoleted
        keepObsolete = set(self._cfg.keepObsolete)
        keepObsoleteSource = set(self._cfg.keepObsoleteSource)

        # Remove any packages that are scheduled for removal.
        # NOTE: This should always be done before adding packages so that
        #       any packages that move between sources will be removed and
        #       then readded.
        if requiredRemovals:
            log.info('removing the following packages from the managed '
                'group: %s' % ', '.join(requiredRemovals))
            for pkg in requiredRemovals:
                group.removePackage(pkg, missingOk=True)
        if removeObsoleted:
            log.info('removing any of obsoleted packages from the managed '
                'group: %s' % ', '.join(removeObsoleted))
            for pkg in removeObsoleted:
                group.removePackage(pkg, missingOk=True)

        # Find and add new packages
        self._addNewPackages(group)

        # Modify any extra groups to match config.
        self._modifyGroups(updateId, group)

        # Get timestamp version.
        # Changing the group version to be more granular than just day
        # This is to avoid building the same group over and over on the
        # same day...
        version = time.strftime('%Y.%m.%d_%H%M.%S', time.gmtime(time.time()))

        # Build groups.
        log.info('setting version %s' % version)
        group.version = version

        group = group.commit()
        grpTrvMap = group.build()

        # Promote groups
        log.info('promoting group %s ' % group.version)
        toPromote = [ x for x in itertools.chain(grpTrvMap.itervalues()) ]
        promoted = self._updater.publish(toPromote, toPromote)

        # Report timings
        advTime = time.strftime('%m-%d-%Y %H:%M:%S',
                                    time.localtime(updateId))
        totalTime = time.time() - starttime
        log.info('published group update %s in %s seconds'
            % (advTime, totalTime))

        return promoted

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
