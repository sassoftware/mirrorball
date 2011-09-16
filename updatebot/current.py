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

from conary import versions
from conary.deps import deps

from updatebot import groupmgr
from updatebot.lib import util
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

    def _addNewPackages(self, allNevrasOnLabel, pkgMap, group):
        """
        Add pkgMap to group.
        """
        from repomd.packagexml import _Package as SrcPkg
        def mkNevraObj(nevra):
            # positive this code is somewhere in the mess... 
            # no time to look for it  
            nvr = SrcPkg()
            nvr.name, nvr.epoch, nvr.version, nvr.release, nvr.arch = nevra
            if nvr.epoch is None:
                nvr.epoch = ''
            elif not isinstance(nvr.epoch, str):
                nvr.epoch = str(nvr.epoch)
            return nvr

        for binSet in pkgMap.itervalues():
            pkgs = {}

            addGroup = False
            if not binSet:
                log.warn('Empty bin set. BAD.')
                import epdb; epdb.st()

            nevraMap = self._conaryhelper.getNevras(binSet)

            for conaryVer, nevra in nevraMap.iteritems():
                if nevra:
                    curPkg = mkNevraObj(nevra)
                    labelNevra = [ mkNevraObj(labelNevra) for labelVer, 
                                    labelNevra in allNevrasOnLabel.iteritems() 
                                        if labelVer[0] == conaryVer[0] ] 
                    labelNevra.sort(util.packagevercmp)
                    labelPkg = labelNevra[-1]
                    if group.hasPackage(curPkg.name):
                        if util.packagevercmp(curPkg, labelPkg) == 1:
                            log.info('%s newer than what was on label' % 
                                    "_".join([curPkg.name,curPkg.version,curPkg.release]))
                            addGroup = True
                        else:
                            log.info('later version found on label')
                    else:
                        log.info('new package adding to group')
                        addGroup = True

            if addGroup:

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


        # FOR TESTING WE SHOULD INSPECT THE PKGMAP HERE
        print "REMOVE LINE AFTER TESTING"
        import epdb; epdb.st()

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

    def _getLatestNevraPackageMap(self, nevraMap):
        """
        Take a mapping of nvf to nevra and transform it into nevra to latest
        package nvf.
        """

        nevras = {}
        for (n, v, f), nevra in nevraMap.iteritems():
            # Skip nvfs that don't have a nevra
            if not nevra:
                continue

            # Skip sources
            if v.isSourceVersion():
                continue

            # Repack nevra subbing '0' for '', since yum metadata doesn't
            # represent epochs of None.
            if nevra[1] == '':
                nevra = (nevra[0], '0', nevra[2], nevra[3], nevra[4])

            pkgNvf = (n.split(':')[0], v, f)
            nevras.setdefault(nevra, set()).add(pkgNvf)

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
        targetNevras = helper.getNevrasForLabel(self._cfg.targetLabel)
        log.info('querying source nevras')
        sourceNevras = helper.getNevrasForLabel(helper._ccfg.buildLabel)

        # Massage nevra maps into nevra -> latest package nvf
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

        # Get a mapping of nvf -> nevra
        sourceNevras = self._updater._conaryhelper.getNevrasForLabel(
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
        sourceNevras = self._updater._conaryhelper.getNevrasForLabel(
            self._updater._conaryhelper._ccfg.buildLabel)

        # Reverse the map and filter out old conary versions.
        sourceLatest = self._getLatestNevraPackageMap(sourceNevras)

        # Find the previous nevra
        srcPkgs = sorted(self._pkgSource.srcNameMap.get(srcPkg.name))
        idx = srcPkgs.index(srcPkg) - 1

        # This is a new package
        if idx < 0:
            return (srcPkg.name, None, None)

        binPkgs = [ x for x in self._pkgSource.srcPkgMap[srcPkgs[idx]]
            if x.arch != 'src' ]

        binPkg = binPkgs[0]

        binNVF = sourceLatest[binPkg.getNevra()]
        sourceVersions = self._updater._conaryhelper.getSourceVersions(
            [binNVF, ]).keys()

        assert len(sourceVersions) == 1
        return sourceVersions[0]

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

        # Update package set.
        if updatePkgs:
            updatePkgs.filterPkgs(kwargs.pop('fltr', None))

            for updateSet in updatePkgs:
                log.info('building set of update troves')
                updateTroves = set([ (self._getPreviousNVFForSrcPkg(x), x)
                    for x in updateSet])

                log.info('running update')
                self._update(*args, updateTroves=updateTroves, updatePkgs=True,
                    expectedRemovals=expectedRemovals, **kwargs)

                # The NEVRA maps will be changing every time through. Make sure
                # the clear the cache.
                log.info('dumping conaryhelper cache')
                self._updater._conaryhelper.clearCache()

        log.info('completed package update of %s packages in %s seconds'
            % (len(updatePkgs), starttime-time.time()))

    def buildgroups(self):
        """
        Find the latest packages on the production label by nevra and build a
        group, taking into account any packages that would have been obsoleted
        along the way.
        """

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

        # Generate grpPkgMap

        #grpPkgNameMap = [ (x.name, x.version, x.flavor) for x in group.iterpackages() ]
        # FIXME: should take the list of troves in the group and 
        # query the label to see if newer nevra versions exist 
        # Then add them to the group

        # FIXME: Not implemented yet
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

        pkgMap = self._useOldVersions(updateId, pkgMap)

        # Make sure built troves are part of the group.
        self._addNewPackages(allNevrasOnLabel, pkgMap, group)

        # FOR TESTING WE SHOULD INSPECT THE PKGMAP HERE
        print "Check the pkgMap now"
        import epdb; epdb.st()

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

        # Add promote for group if success
        if grpTrvMap:
            log.info('promoting group %s ' % group.version)
            # Add promote code here

        updateSet.update(pkgMap)

        # Report timings
        advTime = time.strftime('%m-%d-%Y %H:%M:%S',
                                    time.localtime(updateId))
        totalTime = time.time() - startime
        log.info('published update %s in %s seconds' % (advTime, totalTime))
        count += 1

        # Set this breakpoint when you're committing a list of
        # already-built job id's.  (See long comment above.)
        #import epdb ; epdb.st()

        # TESTING
        print "need to check updates set"
        import epdb ; epdb.st()

        # BELOW THIS LINE WILL BE REMOVED

        # FIXME: remove errata crap


        log.info('update completed')
        log.info('applied %s updates in %s seconds'
            % (count, time.time() - startime))

        return updateSet

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
