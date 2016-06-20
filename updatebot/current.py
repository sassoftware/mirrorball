#
# Copyright (c) SAS Institute, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#


"""
Module for doing updates by importing all of the available packages and then
building groups of the latest versions by nevra.
"""

import time
import logging
import itertools

from conary.deps.deps import ThawFlavor
from conary.versions import ThawVersion

from rpmutils import NEVRA

from updatebot.lib import util
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

        # Oh what a lovely hack this is...it allows persistent add removal
        # from the group-model for current mode
        # not sure what happens when we hit 9999999999 timestamp though

        if 9999999999 in self._cfg.addPackage.keys():
            if not addPackages:
                addPackages = {}
            addPkgs = self._cfg.addPackage.get(9999999999, None)
            for pkg in addPkgs:
                for pkgs in addPkgs[pkg]:
                    addPackages.setdefault(pkg, []).append(pkgs)
        if 9999999999 in self._cfg.removePackage.keys():
            if not removePackages:
                removePackages = {}
            remPkgs = self._cfg.removePackage.get(9999999999, None)
            for pkg in remPkgs:
                for pkgs in remPkgs[pkg]:
                    removePackages.setdefault(pkg, []).append(pkgs)

        # Don't taint group model unless something has actually changed.
        if addPackages or removePackages:
            log.info('modifying group model')
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

                # remove all binary names from the group if they match
                # the version of the src pkg

                binNames = set([ x.name for x in nevraMap[nevra] ])

                for name in binNames:
                    if name in [ x.name for x in group.iterpackages() ]:
                        group.removePackage(name)

        return group

    def _removeObsoletedSource(self, updateId, group):
        # Handle the case of a pkg source being obsoleted and combined into
        # another src rpm (thank you SLES) so we remove all the
        # binaries from that source from the group model
        # _addNewPackages will handle adding the new changes
        # as long as we do this function before it
        if updateId in self._cfg.removeObsoletedSource:
            # get nevras from the config
            nevras = self._cfg.removeObsoletedSource[updateId]

            # get a map of source nevra to binary package list.
            nevraMap = dict((x.getNevra(), y) for x, y in
                            self._pkgSource.srcPkgMap.iteritems()
                            if x.getNevra() in nevras)

            for nevra in nevras:
                # if for some reason the nevra from the config is not in
                # the pkgSource, raise an error.
                if nevra not in nevraMap:
                    raise UnknownRemoveSourceError(nevra=nevra)

                # remove all binary names from the group if they match
                # the version of the src pkg

                binNames = set([ x.name for x in nevraMap[nevra] ])

                for name in binNames:
                    if name in [ x.name for x in group.iterpackages() ]:
                        group.removePackage(name)

        return group

    def _requiredRemovals(self, updateId, group):
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

        return group

    def _keepObsolete(self, updateId, group):

        # Keep Obsoleted
        keepObsolete = set(self._cfg.keepObsolete)
        keepObsoleteSource = set(self._cfg.keepObsoleteSource)

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

            # Skip sources.
            if nvf[1].isSourceVersion():
                continue

            # Skip nvfs that don't have a nevra
            if not nevra:
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
            nevras.setdefault(nevra, dict()).setdefault(nvf[1], set()).add(nvf)

        ret = {}
        for nevra, vs in nevras.iteritems():
            ret[nevra] = vs[sorted(vs)[-1]]

        return ret

    def _getPromotePackages(self):
        """
        Get the packages that have beeen built on the buildLabel, but have yet
        to be promoted to the target label. You should only run accross these if
        the promote step in the package build failed.
        """

        helper = self._updater._conaryhelper

        toPromote = set()

        if self._cfg.targetLabel.label() == helper._ccfg.buildLabel:
            log.info('Target and Source labels match... no need to promote')
            return toPromote

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

        for nevra, nvfs in sourceLatest.iteritems():
            # nevra has not been promoted.
            if nevra not in targetLatest:
                toPromote.union(nvfs)

            # the conary package containing this nevra has been rebuilt.
            for nvf in nvfs:
                if nvf not in targetClonedFrom:
                    toPromote.add(nvf)

        return toPromote

    def _getUpdatePackages(self, sourceNevras=None, sourceLatest=None):
        """
        Compare the upstream yum repository and the conary repository to figure
        out what sources need to be updated.
        """

        start = time.time()

        # Get a mapping of nvf -> nevra
        # And reverse the map and filter out old conary versions.
        if not sourceNevras or not sourceLatest:
            sourceNevras, sourceLatest = self._getSourceNevraLatestMaps()


        # HACK FOR RHEL5CLIENT
        # Another hack for rhel 5 client workstation
        parent = False
        if self._cfg.topParentSourceGroup:
            parent = True
            targetNevras = self._getNevrasForLabel(self._cfg.targetLabel)
            targetLatest = self._getLatestNevraPackageMap(targetNevras)

        explicitIgnoreSources = set([ x for x in 
            itertools.chain(*self._cfg.ignoreSourceUpdate.values()) ])


        # Iterate over all of the available source rpms to find any versions
        # that have not been imported into the conary repository.
        toUpdate = set()

        toUpdateMap = {}

        for binPkg, srcPkg in self._pkgSource.binPkgMap.iteritems():

            # Skip updating pkg if explicitly ignored
            if srcPkg.getNevra() in explicitIgnoreSources:
                log.warn('explicitly ignoring %s in %s' % (binPkg, srcPkg))
                continue

            # Skip over source packages
            if binPkg.arch == 'src':
                continue


            # HACK for RHEL5CLIENT REMOVE
            if parent:
                if binPkg.getNevra() not in targetLatest:
                    toUpdateMap.setdefault(srcPkg, set()).add(binPkg)
                    toUpdate.add(srcPkg)
                    continue


            #if binPkg.getNevra() not in sourceLatest:
            if NEVRA(*binPkg.getNevra()) not in sourceLatest:
                log.debug('UPDATING : %s' % binPkg)
                toUpdateMap.setdefault(srcPkg, set()).add(binPkg)
                toUpdate.add(srcPkg)

        # add a source to a specific bucket, used to "promote" newer versions
        # forward.
        if self._updateId in self._cfg.addSource:
            nevras = dict([ (x.getNevra(), x)
                         for x in self._pkgSource.srcPkgMap ])

            sources = set([nevras[x] for x in self._cfg.addSource[self._updateId]])
            for sPkg in sources:
                if sPkg in self._pkgSource.srcPkgMap:
                    for bPkg in self._pkgSource.srcPkgMap[sPkg]:
                        if bPkg.arch == 'src':
                            continue
                        toUpdateMap.setdefault(sPkg, set()).add(bPkg)
                    toUpdate.add(sPkg)
                else:
                    log.warn('addSource failed for %s' % str(sPkg))

        log.info('Elapsed Time : %s' % (time.time() - start))


        return UpdateSet(toUpdate)


    def _getSourceNevraLatestMaps(self):
        """
        Return sourceNevra and sourceLatest maps
        """

        start = time.time()

        log.info('Creating sourceNevras Map : %s' % start)

        # Get a mapping of nvf -> nevra
        sourceNevras = self._getNevrasForLabel(
                self._updater._conaryhelper._ccfg.buildLabel)

        log.info('Found sourceNevras : %s' % (time.time() - start))

        # Reverse the map and filter out old conary versions.
        sourceLatest = self._getLatestNevraPackageMap(sourceNevras)

        log.info('Created sourceLatest : %s' % (time.time() - start))

        return sourceNevras, sourceLatest

    def _getUpdateTroveSets(self, srcPkgs, sourceNevras=None, sourceLatest=None):
        """
        Takes a list of srcsPkgs 
        Figures out what this source package was meant to update.
        """

        if not sourceNevras or not sourceLatest:
            sourceNevras, sourceLatest = self._getSourceNevraLatestMaps()

        updateSet = set()
        
        for srcPkg in srcPkgs:
            updateSet.add((self._getPreviousNVFForSrcPkg(srcPkg, sourceNevras, sourceLatest), srcPkg))
        #import epdb;epdb.st()
        log.info('Update Set contains %s pkgs' % len(updateSet))
        return updateSet

    def _getPreviousNVFForSrcPkg(self, srcPkg, sourceNevras=None, sourceLatest=None):
        """
        Figure out what this source package was meant to update.
        """

        if not sourceNevras or not sourceLatest:
            sourceNevras, sourceLatest = self._getSourceNevraLatestMaps()

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

                binNVFs = sourceLatest[binPkg.getNevra()]
                sourceVersions = self._updater._conaryhelper.getSourceVersions(
                    binNVFs).keys()

                assert len(set(sourceVersions)) == 1
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
            updateId = 0
        else:
            updateId = group.errataState

        # Get the latest errata state, increment if the source has been built.
        if group.hasBinaryVersion():
            group.errataState += 1
            updateId = group.errataState

        # For debuging
        self._updateId = updateId

        log.info('UpdateID is %s' % self._updateId)

        # Load package source.
        self._pkgSource.load()

        log.info('starting update run')

        starttime = time.time()

        # Figure out what packages still need to be promoted.
        promotePkgs = self._getPromotePackages()

        # Go ahead and promote any packages that didn't get promoted during the
        # last run or have been rebuilt since then.
        if promotePkgs:
            log.info('found %s packages that need to be promoted' %
                len(promotePkgs))
            if 'rhel-5-client-workstation' not in str(self._cfg.topSourceGroup):
                self._updater.publish(promotePkgs, promotePkgs, self._cfg.targetLabel)


        # Figure out what packages need to be updated.
        # These will be used later so lets do this once
        sourceNevras, sourceLatest = self._getSourceNevraLatestMaps()

        updatePkgs = self._getUpdatePackages(sourceNevras, sourceLatest)

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

                log.info('running update')

                log.info('WORKING ON %s UPDATES' % len(updateSet))

                chunks = self._cfg.chunkSize

                chunk = lambda ulist, step:  map(lambda i: ulist[i:i+step],
                            xrange(0, len(ulist), step))
                
                log.info('building set of update troves')

                for upSet in chunk(updateSet, chunks):
                    
                    log.info('Working on upSet : %s' % len(upSet))

                    updateTroves = self._getUpdateTroveSets(upSet, sourceNevras, sourceLatest)

                    log.info('Current Chunk Size : %s' % len(updateTroves))

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
        log.info('retrieving nevras for build label')
        nevraMap = self._getNevrasForLabel(
             self._updater._conaryhelper._ccfg.buildLabel)

        # Reverse the map and filter out old conary versions.
        log.info('getting latest nevra packages')
        latest = self._getLatestNevraPackageMap(nevraMap)

        # Get all of the sources for the possible packages
        log.info('getting source versions for all packages')
        allSources = self._updater._conaryhelper.getSourceVersions(
            nevraMap.keys())

        # The above gets us every binary version that was ever built from a
        # source, we need the latest version of each package that was
        # generated from a given source.
        srcPkgs = {}
        for src, bins in allSources.iteritems():
            nameMap = {}
            for n, v, f in bins:
                nameMap.setdefault(n, dict()).setdefault(v, set()).add(f)
            reduced = set()
            for n, vs in nameMap.iteritems():
                v = sorted(vs)[-1]
                for f in vs[v]:
                    reduced.add((n, v, f))
            srcPkgs[src] = reduced

        toAdd = {}
        toRemove = set()

        ##
        # Find the latest NEVRAs available.
        ##

        # index nevras by name/arch so that we can find the latest version
        names = {}
        for nevra, nvfs in latest.iteritems():
            names.setdefault(nevra.name, dict()).setdefault(nevra.evr,
                dict())[nevra] = nvfs

        # Find the latest nevras.
        actualLatest = {}
        for name, vercmpd in names.iteritems():
            lt = sorted(vercmpd.keys(), cmp=util.packagevercmp)[-1]
            for nevra, nvfs in vercmpd[lt].iteritems():
                for nvf in nvfs:
                    actualLatest[nvf] = nevra

        ##
        # Add latest NEVRAs by source to make sure we don't add NEVRAs that
        # reference more than one source version.
        ##

        # Map the latest nevra nvfs to conary sources.
        latestSources = self._updater._conaryhelper.getSourceVersions(
            actualLatest.keys())

        # Map by name so that we can find duplicate versions
        srcMap = {}
        for src, bins in latestSources.iteritems():
            srcMap.setdefault(src[0], set()).add(src)

        for name, srcs in srcMap.iteritems():
            # Take the easy way out if there is only one source version of
            # this name.
            if len(srcs) == 1:
                for bin in srcPkgs[list(srcs)[0]]:
                    toAdd.setdefault((bin[0], bin[1]), set()).add(bin[2])
                continue

            # Now we have to work reasonably hard to find a nevra that we can
            # use to sort source versions since we don't know what source nevra
            # maps to a particular conary source version.
            #
            # FIXME: This is probably a good place for a conary feature to
            #        source source nevras in trove info in the binary packages.
            #        We would probably need to fall back to the manifest in the
            #        source if the trove info wasn't there.

            # find the latest source by nevra
            fullSrcs = dict([ (x, srcPkgs[x]) for x in srcs ])
            # find a common binary across all source versions
            binnames = {}
            for src, bins in fullSrcs.iteritems():
                # only consider the sources that we are concerned with.
                if src not in srcs:
                    continue
                for bin in bins:
                    binnames.setdefault((bin[0], bin[2]), dict())[bin] = src

            common = None
            for binname, bind in binnames.iteritems():
                if len(bind) == len(srcs):
                    common = bind
                    break

            # If we get here and common is None, that means that there were no
            # common pacakges between the source versions. This happens in RHEL
            # with some of the kmod packages. I guess assume that the conary
            # source version is good enough for sorting?
            if common is None:
                # Need better sorting here as on some nevra we were coming up with wrong ver 
                # and we end up with lower version that is already in the group
                # of course this causes us to pop it from the toAdd list... well
                # we have some new pkgs with the latest version slip in because they were not in the 
                # group to begin with so we end up with a set of older pkgs and a few new ones
                # This causes us to freak out during sanity check with conflict sources

                pkgName = name.split(':')[0]

                # Check to see if we can find the name in the list of srcrpms
                if pkgName in self._pkgSource.srcNameMap:
                    # lets get the latest srcrpm so we can do a rpmcmp
                    ltsnevra = sorted(self._pkgSource.srcNameMap.get(pkgName))[-1]

                    ltsnvf = None
                    # now look up a conary version for this
                    #if ltsnevra.name in nevraMap:
                    if [ x for x in nevraMap if ltsnevra.name in x ]:
                        ltsnvfs = [ x for x,y in nevraMap.iteritems()
                                if (ltsnevra.name,ltsnevra.epoch,ltsnevra.version,ltsnevra.release) ==
                                (y.name,y.epoch,y.version,y.release) ]
                    else:
                        # Sometimes they don't match up at so we will try another method
                        # This can fail sometimes so we break out the steps...
                        ltsnvfs = [ x for x,y in nevraMap.iteritems() 
                                if y.name.startswith(ltsnevra.name) and 
                                (ltsnevra.epoch,ltsnevra.version,ltsnevra.release) == 
                                (y.epoch,y.version,y.release)]
                    if ltsnvfs:
                        ltsnvf = sorted(ltsnvfs)[-1]

                    # now get the source for the conary verison if ltsnvf
                    if ltsnvf:
                        lts = [ x for x,y in allSources.iteritems() if ltsnvf in y][-1]
                    else:
                        # I give up
                        # this is last resort
                        lts = sorted(srcs)[-1]
                else:
                    # I give up
                    # this is last resort
                    lts = sorted(srcs)[-1]

            else:
                # now lookup the nevras for the versions of this binary so
                # that we can determine which source is latest.
                nvmap = {}
                for bin, src in common.iteritems():
                    nvmap.setdefault(nevraMap[bin], set()).add(src)

                lts = sorted(nvmap[sorted(nvmap, cmp=util.packagevercmp)[-1]])[-1]

            for bin in fullSrcs.get(lts):
                toAdd.setdefault((bin[0], bin[1]), set()).add(bin[2])

        ##
        # Now to remove all of the things that are already in the group from
        # the toAdd dict.
        ##

        grpPkgs = {}
        # This list is for debugging process.
        removedPkgs = []

        for pkg in group.iterpackages():
            name = str(pkg.name)
            version = ThawVersion(str(pkg.version))
            flavor = ThawFlavor(str(pkg.flavor))

            grpPkgs.setdefault((name, version), set()).add(flavor)

        for nv, fs in grpPkgs.iteritems():
            if nv in toAdd and toAdd[nv] == fs:
                log.warn('REMOVING %s %s from toAdd' % (nv, fs))
                rem = toAdd.pop(nv)
                removedPkgs.append((nv,rem))


        ##
        # We are going to put together a list of all the removed pkgs
        # it is needed to check the group for stuff we want out
        ## 

        removeObsoleted = set([ x for x in
            itertools.chain(*self._cfg.removeObsoleted.values()) ])
        updateRemovesPackage = set([ x for x in
            itertools.chain(*self._cfg.updateRemovesPackages.values()) ])

        removed = removeObsoleted | updateRemovesPackage

        ##
        # TODO: Need to add function for updateReplacesPackages
        ##
        updateReplacesPackage = set([ x for x in
            itertools.chain(*self._cfg.updateReplacesPackages.values()) ])

        #log.info(updateReplacesPackage)

        ##
        # Iterate over the group contents, looking for any packages that may
        # have been rebuilt, but the nevra stayed the same.
        ##

        for (n, v), fs in grpPkgs.iteritems():

            # Make sure we still want the package
            if n in removed:
                toRemove.add((n, v, f))
                continue

            for f in fs:
                # Get the nevra for this name, version, and flavor
                nevra = nevraMap.get((n, v, f))

                # If the package is already in the toAdd map, skip over it.
                if [ x for x in toAdd
                    if x[0] == n and f in toAdd[(x[0], x[1])] ]:
                    log.warn('%s %s is already in the toAdd map' % (n,f))
                    continue

                # Found a package that isn't actually attached to a nevra,
                # remove it.
                if nevra is None and not [ x for x in nevraMap
                    if x[0] == n and x[2] == f ]:
                    #log.warn('%s %s isnt actually attached to a nevra' % (n,f))
                    toRemove.add((n, v, f))
                    continue

                # FIXME: This is a hack to skip packages in the group from the 
                # devel label. We could load the clonedFromMap and do all kinds 
                # of checks but I think this section should be refactored 
                # instead of adding code

                if nevra is None and [ x for x in nevraMap 
                    if x[0] == n and x[2] == f ]:
                    continue

                # if we get here and are still none blow up
                assert nevra

                # Now find the latest nvf for this nevra.
                nvfs = latest.get(nevra)
                # If the latest nevra nvf is newer than what is in the
                # group, replace it.
                #if v < lt[1]:
                if v < list(nvfs)[0][1]:
                    for n2, v2, f2 in nvfs:
                        toAdd.setdefault((n2, v2), set()).add(f2)

        ##
        # Check to make sure we aren't adding back a package that was previously
        # removed.
        ##

        newPkgs = dict([ (x[0], x) for x in toAdd
            if x[0] not in [ y[0] for y in grpPkgs ] ])

        # Here we use the removed that we put together earlier
        #

        for name in removed:
            if name in newPkgs:
                rem = toAdd.pop(newPkgs[name])
                removedPkgs.append((name, rem))

        ##
        # Remove any packages that were flagged for removal.
        ##

        log.info('removing pkgs flagged for removal')

        for n, v, f in toRemove:
            log.info('removing %s[%s]' % (n, f))
            group.removePackage(n, flavor=f)

        ##
        # Actually add the packages to the group model.
        ##

        log.info('adding newer versions of pkgs to the group model')


        for (name, version), flavors in toAdd.iteritems():
            #for f in flavors:
            #    log.info('adding %s=%s[%s]' % (name, version, f))
            group.addPackage(name, version, flavors)



    def _mangleGroups(self, group):
        """
        Map all packages in the group to packages on the prod label
        using the clonedFrom information
        """

        log.info('mangling the group model')

        grpPkgs = {}

        toProd = {}

        toRemove = set()

        parent = False

        clonedFromMap = dict(self._updater._conaryhelper.getClonedFromForLabel(self._cfg.targetLabel))

        for pkg in group.iterpackages():
            if not pkg.version:
                continue
            name = str(pkg.name)
            version = ThawVersion(str(pkg.version))
            flavor = ThawFlavor(str(pkg.flavor))

            grpPkgs.setdefault((name, version), set()).add(flavor)


        for (name, version), flavors in grpPkgs.iteritems():
            for flavor in flavors:
                # Get the nevra for this name, version, and flavor
                nevra = clonedFromMap.get((name, version, flavor))

                # If the package is already in the toAdd map, skip over it.
                if [ x for x in toProd
                    if x[0] == name and flavor in toProd[(x[0], x[1])] ]:
                    log.warn('%s %s is already in the toProd map' % (name,flavor))
                    continue


                # Package didn't change not sure this should happen
                if not nevra and (name,version,flavor) in clonedFromMap.values():
                    continue

                # Another hack for rhel 5 client workstation
                if self._cfg.topParentSourceGroup:
                    parent = True

                if 'rhel-5-client-workstation' in str(self._cfg.topSourceGroup):
                    parent = True

                if not nevra and parent:
                    log.warn('Child platform')
                    for original, clone in clonedFromMap.iteritems(): 
                        if (name == original[0] and 
                            version.trailingRevision() == original[1].trailingRevision() 
                            and flavor == original[2]):
                            log.warn('adding %s' % str(clone))
                            n2, v2, f2 = clone
                            toProd.setdefault((n2, v2), set()).add(f2)
                            toRemove.add((name, version, flavor))
                            break
                    continue

                # Feels like a hack for RHEL4AS... might revisit this later
                #if not flavor.thaw():
                #    log.warn('No flavor for %s %s %s' % (name, version, flavor))
                #    for original, clone in clonedFromMap.iteritems(): 
                #        if original[0] == name and original[1] == version:
                #            n2, v2, f2 = clone
                #            toProd.setdefault((n2, v2), set()).add(f2)
                #    toRemove.add((name, version, flavor))
                #    continue

                toRemove.add((name, version, flavor))

                n2, v2, f2 = nevra
                toProd.setdefault((n2, v2), set()).add(f2)

        ##
        # Remove any packages that were flagged for removal.
        ##

        for n, v, f in toRemove:
            log.info('removing %s[%s]' % (n, f))
            group.removePackage(n, flavor=f)

        ##
        # Actually add the packages to the group model.
        ##

        for (name, version), flavors in toProd.iteritems():
            for f in flavors:
                log.info('adding %s=%s[%s]' % (name, version, f))
            group.addPackage(name, version, flavors)

        return group


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

        # For debuging
        self._updateId = updateId
        log.info('UpdateID is %s' % self._updateId)

        # Figure out what packages still need to be promoted.
        promotePkgs = self._getPromotePackages()

        # Go ahead and promote any packages that didn't get promoted during the
        # last run or have been rebuilt since then.
        if promotePkgs:
            log.info('found %s packages that need to be promoted' %
                len(promotePkgs))
            if 'rhel-5-client-workstation' not in str(self._cfg.topSourceGroup):
                self._updater.publish(promotePkgs, promotePkgs, self._cfg.targetLabel)

        # Remove any undesired sources from the group model
        # Particularly handy with SLES where suddenly a src rpm is now 
        # built by another src rpm and it is obsolete
        self._removeObsoletedSource(updateId, group)

        # Find and add new packages
        self._addNewPackages(group)

        # Execute required removals
        self._requiredRemovals(updateId, group)

        # Remove source function from cfg
        self._removeSource(updateId, group)

        # Keep Obsolete
        self._keepObsolete(updateId, group)

        # Mangle the devel group to ref packages on the prod label
        # so we can promote...
        if max(self._cfg.sourceLabel) != self._cfg.targetLabel:
            log.info('Target and Source labels differ... mangling group')
            self._mangleGroups(group)

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
        trvMap = {}
        promoted = None

        # Promote groups
        if max(self._cfg.sourceLabel) != self._cfg.targetLabel:
            log.info('promoting group %s ' % group.version)
            toPromote = []
            for grpPkgs in grpTrvMap.itervalues():
                for grpPkg in grpPkgs:
                    toPromote.append((grpPkg[0],grpPkg[1],grpPkg[2]))

            promoted = self._updater.publish(toPromote, toPromote, self._cfg.targetLabel)

        if promoted:
            for trv in promoted:
                n, v , f = trv
                trvMap.setdefault(n, set()).add((n,v,f))

        # Report timings
        advTime = time.strftime('%m-%d-%Y %H:%M:%S',
                                    time.localtime(updateId))
        totalTime = time.time() - starttime
        log.info('published group update %s in %s seconds'
            % (advTime, totalTime))

        return trvMap

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
