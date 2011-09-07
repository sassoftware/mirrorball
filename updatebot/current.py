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
from updatebot import conaryhelper
from updatebot.lib import util
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
from updatebot.errors import UnhandledUpdateError

# FIXME: update the logger for current mode
#log = logging.getLogger('updatebot.ordered')
log = logging.getLogger('updatebot.current')

class Bot(BotSuperClass):
    """
    Implement package driven create/update interface.
    """

    _updateMode = 'current'

    _create = BotSuperClass.create
    _update = BotSuperClass.update
    # REMOVED errataSource from __init__
    def __init__(self, cfg):
        BotSuperClass.__init__(self, cfg)
        # FIXME: remove errata stuff
        #self._errata = errata.ErrataFilter(self._cfg, self._ui, self._pkgSource,
        #    errataSource)
        
        self._groupmgr = groupmgr.GroupManager(self._cfg, self._ui,
            useMap=self._pkgSource.useMap)
        
        self._conaryhelper = conaryhelper.ConaryHelper(self._cfg)
        
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
        if group.errataState == 'None':
            group.errataState = None

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
            self._modifyGroups(0, group)
            group.errataState = '0'
            group.version = '0'
            group = group.commit()
            group.build()

        return pkgMap, failures

    def _addNewPackages(self, allPkgVer, pkgMap, group):
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
                if group.hasPackage(name):
                    # This seems superfluous as we are always 
                    # going to take the latest from the label 
                    # and the pkg should already be on the label
                    curVer = str(version.trailingRevision().version)
                    last = allPkgVer[name]
                    last.sort(util.rpmvercmp)
                    latestVer = last[-1]
                    if util.rpmvercmp(curVer, latestVer) != -1:
                        log.info('adding %s=%s' % (name, version))
                        for f in flavors:
                            log.info('\t%s' % f)
                        group.addPackage(name, version, flavors)
                else:
                    log.info('adding %s=%s' % (name, version))
                    for f in flavors:
                        log.info('\t%s' % f)
                    group.addPackage(name, version, flavors)

        # FOR TESTING WE SHOULD INSPECT THE PKGMAP HERE
        print "REMOVE LINE AFTER TESTING"
        import epdb; epdb.st()


    def _getAllPkgVersionsLabel(self):
        """
        get all versions of a package from the buildLabel 
        and return 2 dictionaries
        allPackageVersions
        allSourceVersions
        """

        log.info('querying buildLabel %s for all committed packages' %
                 self._updater._conaryhelper._ccfg.buildLabel)

        allPackageVersions = {}

        # Get all versions of all on buildLabel committed to repo.
        allPkgVersions = self._updater._conaryhelper._repos.getTroveVersionsByLabel(
                                {None: {self._updater._conaryhelper._ccfg.buildLabel: None}})

        for binary, versions in allPkgVersions.iteritems():

            if ( binary.endswith(':debuginfo') or 
                binary.endswith(':source')):
                 continue

            allPackageVersions[binary] = [ x.versions[1].version 
                                                for x in versions.keys() ]


        allSourceVersions = {}

        # Build dict of all source versions found in repo.
        for source, versions in allPkgVersions.iteritems():
            if source.endswith(':source'):
                allSourceVersions[source.replace(':source', '')] = [ x.versions[1].version 
                                                                        for x in versions.keys() ]


        return allPackageVersions, allSourceVersions


    def _diffRepos(self, allVersions, pkgSrcType=None, debug=0):
        """
        Diff the yum/rpm repo vs the label and return lists
        @pkgSrcType = 'bin' or None -- At this time no need for binary  
        @allSource = self._pkgSource.srcNameMap or self._pkgSource.binNameMap
        @toUpdate = [(rpm)] set of rpms to be updated
        @toCreate = [(rpm)] set of rpms to be created
        """
        
        allSource = self._pkgSource.srcNameMap
        
        if pkgSrcType:
            allSource = self._pkgSource.binNameMap
            
        toUpdate = []
        toCreate = []

        for pkgName, pkgSet in allSource.iteritems():
            if len(pkgSet) == 0:
                continue

            pkgList = list(pkgSet)
            pkgList.sort()

            for pkgPkg in pkgList:
                onLabel = []
                log.info('Working on %s package' % pkgPkg)

                version = util.srpmToConaryVersion(pkgPkg)
                #version = pkgPkg.getConaryVersion() # Only works on src
             
                # skip special packages
                if self._updater._fltrPkg(pkgPkg.name):
                    continue               

                # FAST lookup
                if pkgPkg.name in allVersions:
                    onLabel = [ x for x in allVersions[pkgPkg.name] if
                                                x == version ] 

                # This is not the way to do this
                # Use for debuging only 
                # maybe look up by sha1 sum as well...               
                # SLOW  -- Really this is slow
                if debug: 
                    log.debug('looking up %s on the label' % pkgPkg)
                    onLabel = self._conaryhelper.findTrove((pkgPkg.name, 
                                               version, None))

                if onLabel:
                    log.info('MATCH:version %s of %s  already on the label'
                                % (version, pkgPkg.name))
                    continue

                log.info('Version %s %s not on label adding to update'
                            % (version, pkgPkg.name))
                if pkgPkg.name not in allVersions:
                    log.warn('%s is a new pkg adding to create' % pkgPkg.name)
                    toCreate.append(pkgPkg)
                else:
                    log.info('%s added to update list' % pkgPkg)
                    toUpdate.append(pkgPkg)
                    
        return toUpdate, toCreate

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


    def update(self, *args, **kwargs):
        """
        Handle update case.
        """

        # Load specific kwargs
        restoreFile = kwargs.pop('restoreFile', None)
        checkMissingPackages = kwargs.pop('checkMissingPackages', True)
        
        # Generate an updateId
        #updateId = int(time.time())
        groupId = int(time.time())

        # Generate a today ID for config file.
        # Not sure how to handle this yet
        # This would make it easier to control groups built on the 
        # same day...
        updateId = int(time.mktime(time.strptime(time.strftime('%Y%m%d', 
                                        time.gmtime(time.time())), '%Y%m%d')))

        # Get current group
        group = self._groupmgr.getGroup()

        # Get current timestamp
        current = group.errataState
        if current is None:
            raise PlatformNotImportedError

        # Check to see if there is a binary version if the current group.
        # This handles restarts where the group failed to build, but we don't
        # want to rebuild all of the packages again.
        #if not group.hasBinaryVersion():
        #    group.build()

        # Load package source.
        self._pkgSource.load()

        log.info('starting update run')

        count = 0
        startime = time.time()
        updateSet = {}
        
        allPackageVersions, allSourceVersions = self._getAllPkgVersionsLabel()

        srcUpdate, srcCreate = self._diffRepos(allVersions=allSourceVersions, debug=0)

        # TESTING
        #print "need to check toUpdate"
        #import epdb ; epdb.st() 

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

        updates = set()

        if srcUpdate:
            updates.update(srcUpdate)    
        
        if srcCreate: 
            updates.update(srcCreate)

        # If recovering from a failure, restore the pkgMap from disk.
        pkgMap = {}
        if restoreFile:
            pkgMap = self._restorePackages(restoreFile)
            restoreFile = None

        # Filter out anything that has already been built from the list
        # of updates.
        upMap = dict([ (x.name, x) for x in updates ])
        for n, v, f in pkgMap:
            if n in upMap:
                updates.remove(upMap[n])

        # Update package set.
        if updates:
            fltr = kwargs.pop('fltr', None)
            if fltr:
                updates = fltr(updates)

            #Only build one pkg. 
            upDates = set()
            upDates.add([ x for x in sorted(updates) ][0])
            # This is to check what we are building before we build it
            

            # FOR TESTING WE SHOULD INSPECT THE PKGMAP HERE
            #print "REMOVE LINE AFTER ALTERNATE REPO SETUP"
            #import epdb; epdb.st()

            pkgMap.update(self._update(*args, updatePkgs=upDates,
                expectedRemovals=expectedRemovals,
                allowPackageDowngrades=allowDowngrades, **kwargs))
            #pkgMap.update(self._update(*args, updatePkgs=updates,
            #    expectedRemovals=expectedRemovals,
            #    allowPackageDowngrades=allowDowngrades, **kwargs))

        # FOR TESTING WE SHOULD INSPECT THE PKGMAP HERE
        #print "REMOVE LINE AFTER TESTING"
        #import epdb; epdb.st()

        # Save package map in case we run into trouble later.
        self._savePackages(pkgMap)

        # Start Group Build

        # Get current group
        group = self._groupmgr.getGroup()

        # Get current timestamp
        current = group.errataState
        if current is None:
            raise PlatformNotImportedError        

        # Generate grpPkgMap

        #grpPkgNameMap = [ (x.name, x.version, x.flavor) for x in group.iterpackages() ]


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
        self._addNewPackages(allPackageVersions, pkgMap, group)

        # FOR TESTING WE SHOULD INSPECT THE PKGMAP HERE
        print "Check the pkgMap now"
        import epdb; epdb.st()

        # Modify any extra groups to match config.
        self._modifyGroups(updateId, group)

        # Get timestamp version.
        #version = time.strftime('%Y.%m.%d_%H%M.%S',time.gmtime(updateId))
        #if not version:
        #    version = 'unknown.%s' % updateId
        # Changing the group version to be mopre granular than just day
        # This is to avoid building the same group over and over on the 
        # same day... 
        version = time.strftime('%Y.%m.%d_%H%M.%S',time.gmtime(groupId))
        if not version:
            version = 'unknown.%s' % groupId

        # Build groups.
        log.info('setting version %s' % version)
        group.version = version

        group = group.commit()
        grpTrvMap = group.build()

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

    def promote(self, enforceAllExpected=True, checkMissingPackages=True):
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

        if checkMissingPackages:
            # Ensure no packages are missing from repository.
            self._errata.sanityCheckOrder()
            missingPackages, missingOrder = self._checkMissingPackages()
            if len(missingPackages):
                raise UnhandledUpdateError(why='missing %s ordered source packages from repository' % len(missingPackages))

        log.info('querying repository for all group versions')
        sourceLatest = self._updater.getUpstreamVersionMap(self._cfg.topGroup)

        log.info('querying target label for all group versions')
        targetLatest = self._updater.getUpstreamVersionMap(
            (self._cfg.topGroup[0], self._cfg.targetLabel, None))

        log.info('querying target label for cloned from information')
        # The targetSpec list tells us if the latest version of each group has
        # been promoted to the target label.
        sourceSpecs = [ x for x in itertools.chain(*sourceLatest.itervalues()) ]
        targetSpecs, failed = self._updater.getTargetVersions(sourceSpecs,
            logErrors=False)
        targetSpecMap = {}
        for spec in targetSpecs:
            ver = spec[1].trailingRevision().getVersion()
            targetSpecMap.setdefault(ver, set()).add(spec)

        log.info('starting promote')

        count = 0
        startime = time.time()

        # Get all updates after the first bucket.
        missing = False
        for updateId, bucket in self._errata.iterByIssueDate(current=-1):
            upver = self._errata.getBucketVersion(updateId)

            if updateId <= self._cfg.errataPromoteAfter:
                log.info('version %s (%s) at or below promotion timestamp threshold (%s), skipping' % (upver, updateId, self._cfg.errataPromoteAfter))
                continue
            # FOR SLES FIX 
            #if upver == '2011.07.13_0800.00': 
            #    import epdb; epdb.st()    
            #if upver >= '2011.07.18_0400.00': 
              #  import epdb; epdb.st()    
            # Don't try to promote buckets that have already been promoted.
            if upver in targetLatest and upver in targetSpecMap:
                log.info('%s found on target label, skipping' % upver)
                continue
            elif upver not in targetSpecMap:
                # FIXME: This log message is confusing.
                log.info('%s found on target label, but newer version '
                         'available on source, will repromote' % upver)

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


            advisories = [ x['name'] for x in
                           self._errata.getUpdateDetail(updateId) ]

            for advisory in advisories:
                # Handle attaching an update that was caused by changes that we
                # made outside of the normal update stream to an existing
                # advisory.
                for nvf in self._cfg.extendAdvisory.get(advisory, ()):
                    srcMap = self._updater.getSourceVersionMapFromBinaryVersion(
                        nvf, labels=self._cfg.platformSearchPath,
                        latest=False, includeBuildLabel=True)
                    assert len(srcMap) == 1
                    srcPkgMap.update(srcMap)

            # These are the binary trove specs that we expect to be promoted.
            expected = self._filterBinPkgSet(
                itertools.chain(*srcPkgMap.itervalues()), exceptions)

            # Get list of extra troves from the config
            extra = self._cfg.extraExpectedPromoteTroves.get(updateId, [])

            def promote():
                # Create and validate promote changeset
                packageList = self._updater.publish(toPromote, expected,
                    self._cfg.targetLabel, extraExpectedPromoteTroves=extra,
                    enforceAllExpected=enforceAllExpected)
                return 0

            rc = watchdog.waitOnce(promote)
            if rc:
                break
            count += 1

        log.info('promote complete')
        log.info('promoted %s groups in %s seconds'
            % (count, time.time() - startime))

    def createErrataGroups(self, rebuildGroups=False):
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

        # Get latest errataState from the targetLabel so that we can
        # fence group building based on the target label state.
        targetGroup = groupmgr.GroupManager(self._cfg, self._ui,
                                            targetGroup=True)
        targetErrataState = targetGroup.latest.errataState

        log.info('starting errata group processing')

        count = 0
        startime = time.time()

        for updateId, updates in self._errata.iterByIssueDate(current=0):
            # Stop if the updateId is greater than the state of the
            # latest group on the production label.
            if updateId > targetErrataState:
                log.info('current updateId (%s) is newer than target label '
                    'contents' % updateId)
                break

            # Make sure the group representing the current updateId has been
            # imported and promoted to the production label.
            version = self._errata.getBucketVersion(updateId)
            if not targetGroup.hasBinaryVersion(sourceVersion=version):
                raise TargetVersionNotFoundError(version=version,
                                                 updateId=updateId)

            log.info('%s: looking up version exceptions' % updateId)
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
            mgr = groupmgr.ErrataGroupManagerSet(self._cfg, self._ui)
            groupNames = self._errata.getNames(updateId)
            for advInfo in self._errata.getUpdateDetail(updateId):
                advisory = advInfo['name']
                log.info('%s: processing' % advisory)

                srcPkgs = self._errata.getAdvisoryPackages(advisory)
                if advisory in self._cfg.brokenErrata:
                    # We expect srcPkgs to be empty for known-broken errata.
                    log.warning('%s: skipping broken advisory' % advisory)
                    continue
                else:
                    assert srcPkgs

                targetGrp = groupmgr.SingleGroupManager(groupNames[advisory],
                    self._cfg, self._ui, targetGroup=True)

                if targetGrp.hasBinaryVersion() and not rebuildGroups:
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
                    # Taghandler components were moved to common label
                    # and packages were rebuilt, so omit them here to
                    # prevent older versions of packages being pulled in
                    # (raising exceptions during commit) due solely to
                    # their taghandler components (which are missing in
                    # the newer versions).
                    if n.endswith(':tagdescription') or n.endswith(':taghandler'):
                        continue
                    n = n.split(':')[0]
                    nvfMap.setdefault((n, v), set()).add(f)

                if rebuildGroups and targetGrp.hasBinaryVersion():
                    # For comparing with rebuilt group model.
                    oldGrp = {}
                    for x in grp.iterpackages():
                        if x.flavor != None:
                            log.info('%s: found flavoring for %s=%s: %s' % (advisory, x.name, x.version, x.flavor))
                        oldGrp.setdefault(x.name,set()).add((x.version,
                                                             x.flavor))

                    packagesToRemove = set()
                    for packageToRemove in grp.iterpackages():
                        packagesToRemove.add(packageToRemove.name)
                    for packageToRemove in packagesToRemove:
                        grp.removePackage(packageToRemove)

                    # Should be empty:
                    if len([ x for x in grp.iterpackages() ]):
                        log.error('%s: group model not empty after pre-rebuild package removal' % advisory)
                        # Change to assertion?
                        import epdb ; epdb.st()

                # Add packages to group model.
                for (n, v), flvs in nvfMap.iteritems():
                    log.info('%s: adding package %s=%s' % (advisory, n, v))
                    for f in flvs:
                        log.info('%s: %s' % (advisory, f))
                    grp.addPackage(n, v, flvs)

                if rebuildGroups and targetGrp.hasBinaryVersion():
                    # Sanity-checking craziness, could use a haircut, perhaps
                    # a move to its own function.
                    newGrp = {}
                    for x in grp.iterpackages():
                        newGrp.setdefault(x.name,set()).add((x.version,
                                                             x.flavor))

                    # Compare old & new.
                    for oldPkg, oldVF in oldGrp.iteritems():
                        for oldV, oldF in oldVF:
                            try:
                                if not newGrp[oldPkg]:
                                    raise KeyError
                            except KeyError:
                                log.error('%s: missing package %s in new group model' % (advisory, oldPkg))
                                import epdb ; epdb.st()
                                continue
                            found = False
                            oldVt = versions.ThawVersion(oldV).trailingRevision().getVersion()
                            for newVF in newGrp[oldPkg]:
                                if not oldF:
                                    newVt = versions.ThawVersion(newVF[0]).trailingRevision().getVersion()
                                    if oldVt == newVt:
                                        log.info('%s: found matching version %s for %s in new group model' % (advisory, newVt, oldPkg))
                                        if oldV != newVF[0]:
                                            log.warning('%s: note difference in %s source/build versions due to rebuilt package: %s != %s' % (advisory, oldPkg, oldV, newVF[0]))
                                        found = True
                                        del newGrp[oldPkg]
                                        break
                                else:
                                    newVt = versions.ThawVersion(newVF[0]).trailingRevision().getVersion()
                                    if oldVt == newVt and oldF == newVF[1]:
                                        log.info('%s: found matching version ' % advisory + '%s and flavor %s ' % (newVt, newVF[1]) + 'for %s in new group model' % oldPkg)
                                        if oldV != newVF[0]:
                                            log.warning('%s: note difference in %s source/build versions due to rebuilt package: %s != %s' % (advisory, oldPkg, oldV, newVF[0]))
                                        found = True
                                        newGrp[oldPkg].remove((newVF[0], oldF))
                                        if not len(newGrp[oldPkg]):
                                            log.info('%s: all versions/flavors matched for %s' % (advisory, oldPkg))
                                            del newGrp[oldPkg]
                                        break
                            if not found:
                                log.error('%s: cannot find %s for %s in new group model' % (advisory, oldV, oldPkg))
                                import epdb ; epdb.st()
                    
                    if len(newGrp):
                        log.error('%s: new group model has extra packages: %s' % (advisory, newGrp))
                        import epdb ; epdb.st()
                    else:
                        log.info('%s: new group model package versions verified to match old group model' % advisory)
                        log.info('%s: (note flavor match between old and new models may have been left unchecked for some packages)' % advisory)
                    
            # Make sure there are groups to build.
            if not mgr.hasGroups():
                log.info('%s: groups already built and promoted' % updateId)
                continue

            log.info('%s: committing group sources' % updateId)

            mgr.commit()

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
