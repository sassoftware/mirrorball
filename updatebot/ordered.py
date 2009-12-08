#
# Copyright (c) 2009 rPath, Inc.
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

import logging

from updatebot import errata
from updatebot import groupmgr
from updatebot.bot import Bot as BotSuperClass

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
        self._errata = errata.ErrataFilter(self._pkgSource, errataSource)
        self._groupmgr = groupmgr.GroupManager(self._cfg)
        self._versionFactory = groupmgr.VersionFactory(self._cfg)

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

    def create(self, *args, **kwargs):
        """
        Handle initial import case.
        """

        # Make sure this platform has not already been imported.
        if self._groupmgr.getErrataState():
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

        # Get current timestamp
        current = self._groupmgr.getErrataState()
        if current is None:
            raise PlatformNotImportedError

        # Load package source.
        self._pkgSource.load()

        updateSet = {}
        for updateId, updates in self._errata.iterByIssueDate(start=current):
            detail = self._errata.getUpdateDetailMessage(updateId)
            log.info('attempting to apply %s' % detail)

            # Update package set.
            pkgMap = self._update(updatePkgs=updates)

            # Store current updateId.
            self._groupmgr.setErrataState(updateId)

            # Find errata group versions.
            errataVersions = set()
            for advisory in self._errata.getUpdateDetail(updateId):
                # advisory names are in the form RHSA-2009:1234
                # transform to a conary version.
                name = advisory['name']
                name = name.replace('-', '_')
                name = name.replace(':', '.')
                name += '_rolling'
                errataVersions.add(name)

            # FIXME: this are probably not the versions that we need
            # Get current set of source names and versions.
            nvMap = self._updater.getSourceVersionMap()
            for n, v, f in pkgMap.iterkeys():
                n = n.split(':')[0]
                nvMap[n] = v
            pkgSet = set(nvMap.items())

            # Build various group verisons.
            for version in (errataVersions +
                            self._groupmgr.getVersions(pkgSet)):
                log.info('setting version %s' % version)
                self._groupmgr.setVersion(version)
                self._groupmgr.build()

            updateSet.update(pkgMap)

        return updateSet
