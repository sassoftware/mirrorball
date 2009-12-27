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

import time
import logging

from updatebot import errata
from updatebot import groupmgr
from updatebot.bot import Bot as BotSuperClass

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

        # Load package source.
        self._pkgSource.load()

        updateSet = {}
        for updateId, updates in self._errata.iterByIssueDate(current=current):
            start = time.time()
            detail = self._errata.getUpdateDetailMessage(updateId)
            log.info('attempting to apply %s' % detail)

            # Update package set.
            pkgMap = self._update(*args, updatePkgs=updates, **kwargs)

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
            if updateId in self._cfg.updateRemovesPackages:
                pkgs = self._cfg.updateRemovesPackages[updateId]
                log.info('removing the following packages from the managed '
                    'group: %s' % ', '.join(pkgs))
                for pkg in pkgs:
                    self._groupmgr.remove(pkg)

            # Make sure built troves are part of group.
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
