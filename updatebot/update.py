#
# Copyright (c) 2008 rPath, Inc.
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
Module for finding packages to update and updating them.
"""

import logging

from rpmvercmp import rpmvercmp
from rpmimport import recipemaker

from updatebot import util
from updatebot.errors import *
from updatebot import conaryhelper

log = logging.getLogger('updatebot.update')

class Updater(object):
    """
    Class for finding and updating packages.
    """

    def __init__(self, cfg, rpmSource):
        self._cfg = cfg
        self._rpmSource = rpmSource

        self._conaryhelper = conaryhelper.ConaryHelper(self._cfg)

        ccfg = self._conaryhelper.getConaryConfig()
        self._recipeMaker = recipemaker.RecipeMaker(ccfg, self._rpmSource)

    def getUpdates(self):
        """
        Find all packages that need updates and/or advisories from a top level
        binary group.
        @return list of packages to send advisories for and list of packages
                to update
        """

        toAdvise = []
        toUpdate = []
        for nvf, srpm in self._findUpdatableTroves(self._cfg.topGroup):
            # Will raise exception if any errors are found, halting execution.
            if self._sanitizeTrove(nvf, srpm):
                toUpdate.append((nvf, srpm))

            # Make sure to send advisories for any packages that didn't get
            # sent out last time.
            toAdvise.append((nvf, srpm))

        log.info('found %s troves to update, and %s troves to send advisories'
                 % (len(toUpdate), len(toAdvise)))
        return toAdvise, toUpdate

    def _findUpdatableTroves(self, group):
        """
        Query a group to find packages that need to be updated.
        @param group: package spec for the top level group to query
        @type group: (name, versionObj, flavorObj)
        @return list of nvf and src package object
        """

        # ((name, version, flavor), srpm)
        troves = []
        for name, version, flavor in self._conaryhelper.getSourceTroves(group):
            name = name.split(':')[0]

            # skip special packages
            if (name.startswith('info-') or
                name.startswith('group-') or
                name in self._cfg.excludePackages):
                continue

            latestSrpm = self._getLatestSource(name)
            latestVer = util.srpmToConaryVersion(latestSrpm)
            curVer = str(version.trailingRevision().version)
            if rpmvercmp(latestVer, curVer) != 0:
                log.info('found potential updatable trove: %s' % ((name, version, flavor), ))
                log.debug('cny: %s, rpm: %s' % (curVer, latestVer))
                # Add anything that has changed, version may have gone
                # backwards if epoch changes.
                troves.append(((name, version, flavor), latestSrpm))
#            else:
#                log.debug('found already up to date trove: %s' % ((name, version, flavor), ))

        log.info('found %s protentially updatable troves' % len(troves))
        return troves

    def _getLatestSource(self, name):
        """
        Get the latest src package for a given package name.
        @param name: name of the package to retrieve
        @type name: string
        @return src package object
        """

        srpms = self._rpmSource.srcNameMap[name]
        srpms.sort(util.packagevercmp)
        return srpms[-1]

    def _sanitizeTrove(self, nvf, srpm):
        """
        Verifies the package update to make sure it looks correct and is a
        case that the bot knows how to handle.

        If an error occurs an exception will be raised, otherwise return a
        boolean value whether to update the source component or not. All
        packages that pass this method need to have advisories sent.

        @param nvf: name, version, and flavor of the source component to be
                    updated
        @type nvf: (name, versionObj, flavorObj)
        @param srpm: src pacakge object
        @type srpm: repomd.packagexml._Package
        @return needsUpdate boolean
        @raises UpdateGoesBackwardsError
        @raises UpdateRemovesPackageError
        """

        needsUpdate = False
        newLocations = [ x.location for x in self._rpmSource.srcPkgMap[srpm] ]
        newNames = [ x.name for x in self._rpmSource.srcPkgMap[srpm] ]
        manifest = [ x.strip() for x in self._recipeMaker.getManifest(nvf[0]) ]
        for line in manifest:
            binPkg = self._rpmSource.locationMap[line]
            srcPkg = self._rpmSource.binPkgMap[binPkg]

            # set needsUpdate if version changes
            if util.packagevercmp(srpm, srcPkg) == 1:
                needsUpdate = True

            # make sure new package is actually newer
            if util.packagevercmp(srpm, srcPkg) == -1:
                raise UpdateGoesBackwardsError(why=(srcPkg, srpm))

            # make sure we aren't trying to remove a package
            if binPkg.name not in newNames:
                raise UpdateRemovesPackageError(why='%s not in %s' % (binPkg.name, newNames))

        return needsUpdate
