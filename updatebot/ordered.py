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
        thawFlavor = deps.ThawFlavor

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

        # FIXME: this should probably be provided by the errata object.
        # Method for sorting versions.
        def verCmp(a, b):
            if a.startswith('RH') and b.startswith('RH'):
                return cmp(a.split('_')[1], b.split('_')[1])
            elif a.startswith('RH') and not b.startswith('RH'):
                return 1
            elif not a.startswith('RH') and b.startswith('RH'):
                return -1
            else:
                return cmp(a, b)

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

            # Save package map in case we run into trouble later.
            self._savePackages(pkgMap)

            # FIXME: we might actually want to do this one day
            # Find errata group versions.
            #errataVersions = self._errata.getVersions(updateId)
            errataVersions = set()

            # Add timestamp version.
            errataVersions.add(self._errata.getBucketVersion(updateId))

            # FIXME: Might want to re-enable this one day.
            # Get current set of source names and versions.
            #nvMap = self._updater.getSourceVersionMap()
            # Add in new names and versions that have just been built.
            #for n, v, f in pkgMap.iterkeys():
            #    n = n.split(':')[0]
            #    nvMap[n] = v
            #pkgSet = set(nvMap.items())
            # Get the major distro verisons from the group manager.
            #majorVersions = self._groupmgr.getVersions(pkgSet)
            #import epdb; epdb.st()

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

            # Build various group verisons.
            #expected = self._flattenSetDict(pkgMap)
            versions = sorted(errataVersions, cmp=verCmp)
            if not versions:
                versions = ['unknown.%s' % updateId, ]
            for version in versions:
                log.info('setting version %s' % version)
                self._groupmgr.setVersion(version)
                grpTrvMap = self._groupmgr.build()

                # FIXME: enable promotes at some point
                #log.info('promoting version %s' % version)
                #toPublish = self._flattenSetDict(grpTrvMap)
                #newTroves = self._updater.publish(
                #    toPublish,
                #    expected,
                #    self._cfg.targetLabel
                #)

                # After the first promote, packages should not be repromoted.
                #expected = set()

            updateSet.update(pkgMap)

            # Report timings
            advTime = time.strftime('%m-%d-%Y %H:%M:%S',
                                    time.localtime(updateId))
            totalTime = time.time() - start
            log.info('published update %s in %s seconds' % (advTime, totalTime))

        return updateSet
