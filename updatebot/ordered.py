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

from updatebot import errata
from updatebot import groupmgr
from updatebot.bot import Bot as BotSuperClass

from updatebot.errors import UnknownRemoveSourceError
from updatebot.errors import PlatformNotImportedError
from updatebot.errors import TargetVersionNotFoundError
from updatebot.errors import PlatformAlreadyImportedError

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
        self._groupmgr = groupmgr.GroupManager(self._cfg)

        if self._cfg.platformSearchPath:
            self._parentGroup = groupmgr.GroupManager(self._cfg,
                                                      parentGroup=True)

    def _addPackages(self, pkgMap):
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
                self._groupmgr.addPackage(name, version, flavors)

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

        # Make sure this platform has not already been imported.
        if self._groupmgr.getErrataState() is not None:
            raise PlatformAlreadyImportedError

        self._pkgSource.load()
        toCreate = self._errata.getInitialPackages()

        pkgMap, failures = self._create(*args, toCreate=toCreate, **kwargs)

        # Insert package map into group.
        self._addPackages(pkgMap)

        # Save group changes if there are any failures.
        if failures:
            self._groupmgr.save()

        # Try to build the group if everything imported.
        else:
            self._groupmgr.setErrataState('0')
            self._groupmgr.setVersion('0')
            self._groupmgr.build()

        return pkgMap, failures

    def update(self, *args, **kwargs):
        """
        Handle update case.
        """

        # Load specific kwargs
        restoreFile = kwargs.pop('restoreFile', None)

        # Get current timestamp
        current = self._groupmgr.getErrataState()
        if current is None:
            raise PlatformNotImportedError

        # Check to see if there is a binary version if the current group.
        # This handles restarts where the group failed to build, but we don't
        # want to rebuild all of the packages again.
        if not self._groupmgr.hasBinaryVersion():
            # grpmgr.build will make sure to refresh the group model and sync
            # up the standard group contents before building.
            self._groupmgr.build()

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
            log.info('found modified updates, validating repository state')
            for advisory, advInfo in changed.iteritems():
                log.info('validating %s' % advisory)
                for srpm in advInfo['srpms']:
                    log.info('checking %s' % srpm.name)
                    # This will raise an exception if any inconsistencies are
                    # detected.
                    self._updater.sanityCheckSource(srpm)

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


            # If recovering from a failure, restore the pkgMap from disk.
            if restoreFile:
                pkgMap = self._restorePackages(restoreFile)
                restoreFile = None

            # Update package set.
            else:
                pkgMap = self._update(*args, updatePkgs=updates,
                    expectedRemovals=expectedRemovals, **kwargs)

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
            self._groupmgr.setErrataState(updateId)

            # Remove any packages that are scheduled for removal.
            # NOTE: This should always be done before adding packages so that
            #       any packages that move between sources will be removed and
            #       then readded.
            if requiredRemovals:
                log.info('removing the following packages from the managed '
                    'group: %s' % ', '.join(requiredRemovals))
                for pkg in requiredRemovals:
                    self._groupmgr.remove(pkg)
            if removeObsoleted:
                log.info('removing any of obsoleted packages from the managed '
                    'group: %s' % ', '.join(removeObsoleted))
                for pkg in removeObsoleted:
                    self._groupmgr.remove(pkg, missingOk=True)

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
                        self._groupmgr.remove(name)

            # Make sure built troves are part of the group.
            self._addPackages(pkgMap)

            # Get timestamp version.
            version = self._errata.getBucketVersion(updateId)
            if not version:
                version = 'unknown.%s' % updateId

            # Build groups.
            log.info('setting version %s' % version)
            self._groupmgr.setVersion(version)
            grpTrvMap = self._groupmgr.build()

            updateSet.update(pkgMap)

            # Report timings
            advTime = time.strftime('%m-%d-%Y %H:%M:%S',
                                    time.localtime(updateId))
            totalTime = time.time() - start
            log.info('published update %s in %s seconds' % (advTime, totalTime))

        return updateSet

    def promote(self):
        pass

    def createErrataGroups(self):
        """
        Create groups for each advisory that only contain the versions of
        packages that were included in that advisory. Once created, promote
        to production branch.
        """

        # Get current timestamp
        current = self._groupmgr.getErrataState()
        if current is None:
            raise PlatformNotImportedError

        # Load package source.
        self._pkgSource.load()

        # Get latest errataState from the targetLabel so that we can fence group
        # building based on the target label state.
        targetGroup = groupmgr.GroupManager(self._cfg, targetGroup=True)
        targetErrataState = targetGroup.getErrataState()

        failures = {}
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
            if not targetGroup.hasBinaryVersion(version=version):
                raise TargetVersionNotFoundError(version=version,
                                                 updateId=updateId)

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

                grp = mgr.newGroup(groupNames[advisory])
                grp.setVersion(version)
                grp.setErrataState(updateId)

                log.info('%s: finding built packages' % advisory)
                binTrvs = set()
                for srcPkg in srcPkgs:
                    binTrvSpecs = \
                        self._updater.getBinaryVersionsFromSourcePackage(srcPkg)

                    # FIXME: Do something here to figure out what version should
                    #        have been promoted from binTrvSpecs. Note that all
                    #        built versions of a package will end up in
                    #        binTrvSpecs, even if they didn't make it into a
                    #        group.

                    targetSpecs, failed = self._updater.getTargetVersions(binTrvSpecs)
                    binTrvs.update(set(targetSpecs))
                    failures.setdefault(advisory, list()).extend(failed)

                binPkgs = {}
                for n, v, f in binTrvs:
                    binPkgs.setdefault(n.split(':')[0], dict()).setdefault(v, set()).add(f)

                for n, vMap in binPkgs.iteritems():
                    assert len(vMap) == 1

                    # FIXME: If there are two versions of the package that have
                    #        been promoted I would expect it to something like
                    #        the case of setroubleshoot where we had to rebuild
                    #        due to our deps changing. This should be mentioned
                    #        in the config and provide an advisory to tie the
                    #        new version to.

                    for v, flvs in vMap.iteritems():
                        log.info('%s: adding package %s=%s' % (advisory, n, v))
                        for f in flvs:
                            log.info('%s: %s' % (advisory, f))
                        grp.addPackage(n, v, flvs)

            log.info('%s: would be building groups here' % advisory)
            #log.info('building groups')
            #trvMap = mgr.build()

            log.info('%s: would be promoting groups here' % advisory)
            #log.info('promoting groups')
            # Setting expected to an empty tuple since we don't expect anything
            # other than groups to be promoted.
            #expected = tuple()
            #toPromote = self._flatenSetDict(trvMap)
            #promoted = self._updater.publish(toPromote, expected,
            #                                 self._cfg.targetLabel)

        import epdb; epdb.st()
