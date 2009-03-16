#
# Copyright (c) 2008-2009 rPath, Inc.
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
Module for driving the update process.
"""

import time
import logging

from updatebot import build
from updatebot import update
from updatebot import pkgsource
from updatebot import advisories

log = logging.getLogger('updatebot.bot')

class Bot(object):
    """
    Top level object for driving update process.
    """

    def __init__(self, cfg):
        self._cfg = cfg

        self._patchSourcePopulated = False

        self._clients = {}
        self._pkgSource = pkgsource.PackageSource(self._cfg)
        self._updater = update.Updater(self._cfg, self._pkgSource)
        self._advisor = advisories.Advisor(self._cfg, self._pkgSource,
                                           self._cfg.platformName)
        self._builder = build.Builder(self._cfg)

    @staticmethod
    def _flattenSetDict(setDict):
        """
        Convert a dictionary with values of sets to a list.
        @param setList: dictionary of sets
        @type setList: [set(), set(), ...]
        @return list of items that were in the sets
        """

        lst = []
        for trvSet in setDict.itervalues():
            lst.extend(list(trvSet))
        return lst

    def create(self, rebuild=False):
        """
        Do initial imports.
        """

        start = time.time()
        log.info('starting import')

        # Populate rpm source object from yum metadata.
        self._pkgSource.load()

        # Build list of packages
        if self._cfg.packageAll:
            toPackage = set()
            for srcName, srcSet in self._pkgSource.srcNameMap.iteritems():
                if len(srcSet) == 0:
                    continue

                srcList = list(srcSet)
                srcList.sort()
                latestSrc = srcList[-1]

                if latestSrc not in self._pkgSource.srcPkgMap:
                    log.warn('not packaging %s, not found in srcPkgMap' % latestSrc.name)
                    continue

                if latestSrc.name in self._cfg.package:
                    log.warn('ignoring %s due to exclude rule' % latestSrc.name)
                    continue

                for binPkg in self._pkgSource.srcPkgMap[latestSrc]:
                    toPackage.add(binPkg.name)

        else:
            toPackage = set(self._cfg.package)

        # Import sources into repository.
        toBuild, fail = self._updater.create(toPackage,
                                             buildAll=rebuild)

        log.info('failed to create %s packages' % len(fail))
        log.info('found %s packages to build' % len(toBuild))

        if not rebuild:
            # Build all newly imported packages.
            trvMap, failed = self._builder.buildmany(toBuild)
        else:
            # ReBuild all packages.
            trvMap = self._builder.buildsplitarch(toBuild)

        log.info('import completed successfully')
        log.info('imported %s source packages' % (len(toBuild), ))
        log.info('elapsed time %s' % (time.time() - start, ))

        return trvMap

    def update(self, force=None):
        """
        Update the conary repository from the yum repositories.
        @param force: list of packages to update without exception
        @type force: list(pkgName, pkgName, ...)
        """

        if force is not None:
            self._cfg.disableUpdateSanity = True
            assert isinstance(force, list)

        start = time.time()
        log.info('starting update')

        # Populate rpm source object from yum metadata.
        self._pkgSource.load()

        # Get troves to update and send advisories.
        toAdvise, toUpdate = self._updater.getUpdates()

        # If forcing an update, make sure that all packages are listed in
        # toAdvise and toUpdate as needed.
        if force:
            advise = list()
            updates = list()
            for pkg in toAdvise:
                if pkg[1].name in force:
                    advise.append(pkg)
            for pkg in toUpdate:
                if pkg[1].name in force:
                    updates.append(pkg)
            toAdvise = advise
            toUpdate = updates

        if len(toAdvise) == 0:
            log.info('no updates available')
            return

        # Populate patch source now that we know that there are updates
        # available.
        self._advisor.load()

        # Check to see if advisories exist for all required packages.
        self._advisor.check(toAdvise)

        # Update source
        for nvf, srcPkg in toUpdate:
            toAdvise.remove((nvf, srcPkg))
            newVersion = self._updater.update(nvf, srcPkg)
            toAdvise.append(((nvf[0], newVersion, nvf[2]), srcPkg))

        # Make sure to build everything in the toAdvise list, there may be
        # sources that have been updated, but not built.
        buildTroves = set([ x[0] for x in toAdvise ])
        trvMap = self._builder.build(buildTroves)

        # Build group.
        grpTrvs = set()
        for flavor in self._cfg.groupFlavors:
            grpTrvs.add((self._cfg.topSourceGroup[0],
                         self._cfg.topSourceGroup[1],
                         flavor))
        grpTrvMap = self._builder.build(grpTrvs)

        # Promote group.
        # We expect that everything that was built will be published.
        expected = self._flattenSetDict(trvMap)
        toPublish = self._flattenSetDict(grpTrvMap)
        newTroves = self._updater.publish(toPublish, expected,
                                          self._cfg.targetLabel)

        # Mirror out content
        self._updater.mirror()

        # Send advisories.
        self._advisor.send(toAdvise, newTroves)

        log.info('update completed successfully')
        log.info('updated %s packages and sent %s advisories'
                 % (len(toUpdate), len(toAdvise)))
        log.info('elapsed time %s' % (time.time() - start, ))
