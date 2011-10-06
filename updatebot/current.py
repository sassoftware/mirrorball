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
        ###
        # Remove any packages that were flagged for removal.
        ##

        for n, v, f in toRemove:
            log.info('removing %s[%s]' % (n, f))
            group.removePackage(n, flavor=f)

        ##
        # Actually add the packages to the group model.
        ##

        for (name, version), flavors in toAdd.iteritems():
            for f in flavors:
                log.info('adding %s=%s[%s]' % (name, version, f))
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

        # Find and add new packages
        self._addNewPackages(group)

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
        toPromote = []
        for grpPkgs in grpTrvMap.itervalues():
            for grpPkg in grpPkgs:
                toPromote.append((grpPkg[0],grpPkg[1],grpPkg[2]))

        promoted = self._updater.publish(toPromote, toPromote, self._cfg.targetLabel)

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
