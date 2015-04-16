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
Module for driving the update process.
"""

import time
import logging
import itertools

from updatebot import build
from updatebot import update
from updatebot import cmdline
from updatebot import pkgsource

from updatebot.errors import InvalidUpdateModeError

log = logging.getLogger('updatebot.bot')

class Bot(object):
    """
    Top level object for driving update process.
    """

    _updateMode = 'latest'

    def __init__(self, cfg):
        self._validateMode(cfg)

        self._cfg = cfg

        self._clientcfg = cmdline.UpdateBotClientConfig()
        self._ui = cmdline.UserInterface(self._clientcfg)

        self._pkgSource = pkgsource.PackageSource(self._cfg, self._ui)
        self._updater = update.Updater(self._cfg, self._ui, self._pkgSource)
        self._builder = build.Builder(self._cfg, self._ui)

    @classmethod
    def _validateMode(cls, cfg):
        if cfg.updateMode != cls._updateMode:
            raise InvalidUpdateModeError(
                mode=cfg.updateMode, expected=cls._updateMode)

    @staticmethod
    def _flattenSetDict(setDict):
        """
        Convert a dictionary with values of sets to a list.
        @param setDict: dictionary of sets
        @type setDict: [set(), set(), ...]
        @return list of items that were in the sets
        """

        return [ x for x in itertools.chain(*setDict.itervalues()) ]

    def _formatBuildTroves(self, buildSet):
        """
        Format a list of trove specs and source package objects into something
        the build subsystem can deal with.
        """

        toBuild = set()
        for (n, v, f), srcPkg in buildSet:
            binaryNames = None
            if srcPkg:
                binaryNames = tuple(self._updater.getPackageFileNames(srcPkg))
            toBuild.add((n, v, f, binaryNames))

        return sorted(toBuild)

    def create(self, rebuild=False, recreate=None, toCreate=None):
        """
        Do initial imports.

        @param rebuild - rebuild all sources
        @type rebuild - boolean
        @param recreate - recreate all sources or a specific list of packages
        @type recreate - boolean to recreate all sources or a list of specific
                         package names
        @param toCreate - set of source package objects to create, implies
                          recreate.
        @type toCreate - iterable
        """

        start = time.time()
        log.info('starting import')

        # Populate rpm source object from yum metadata.
        self._pkgSource.load()

        # Build list of packages
        if toCreate:
            toPackage = None
        elif type(recreate) == list:
            toPackage = set(recreate)
        elif self._cfg.packageAll:
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

                if (latestSrc.name in self._cfg.excludePackages or
                    latestSrc.name in self._cfg.package):
                    log.warn('ignoring %s due to exclude rule' % latestSrc.name)
                    continue

                for binPkg in self._pkgSource.srcPkgMap[latestSrc]:
                    toPackage.add(binPkg.name)

        else:
            toPackage = set(self._cfg.package)


        # Import sources into repository.
        buildSet, parentPkgMap, fail = self._updater.create(
            toPackage,
            buildAll=rebuild,
            recreate=bool(recreate),
            toCreate=toCreate)

        if fail:
            log.error('failed to create %s packages:' % len(fail))
            for pkg, e in fail:
                log.error('failed to import %s: %s' % (pkg, e))
            return {}, fail

        toBuild = self._formatBuildTroves(buildSet)
        log.info('found %s packages to build' % len(toBuild))

        trvMap = {}
        failed = ()

        if len(toBuild):
            if not rebuild or (rebuild and toCreate):
                # Build all newly imported packages.
                trvMap, failed = self._builder.buildmany(toBuild)
                log.info('failed to import %s packages' % len(failed))
                if len(failed):
                    for pkg in failed:
                        log.warn('%s' % (pkg, ))
            else:
                # ReBuild all packages.
                trvMap = self._builder.buildsplitarch(toBuild)
            log.info('import completed successfully')
            log.info('imported %s source packages' % (len(toBuild), ))
        else:
            log.info('no packages found to build, maybe there is a flavor '
                     'configuration issue')

        log.info('elapsed time %s' % (time.time() - start, ))

        # Add any platform packages to the trove map.
        trvMap.update(parentPkgMap)

        return trvMap, failed

    def update(self, force=None, updatePkgs=None, expectedRemovals=None,
        allowPackageDowngrades=None, updateTroves=None,
        keepRemovedPackages=None):
        """
        Update the conary repository from the yum repositories.
        @param force: list of packages to update without exception
        @type force: list(pkgName, pkgName, ...)
        @param updatePkgs: set of source package objects to update
        @type updatePkgs: iterable of source package objects
        @param expectedRemovals: set of packages that are expected to be
                                 removed.
        @param allowPackageDowngrades: list of source nevra tuples to downgrade
                                       from/to.
        @type allowPackageDowngrades: list(list(from srcNevra, to srcNevra), )
        @type expectedRemovals: set of package names
        @param updateTroves: overrides the value of updatePkgs. Set of (n, v, f)
            tuple to update from and source package to update to.
        @type updateTroves: set(((n, v, f), srcPkg))
        @param keepRemovedPackages: list of package nevras to keep even though
                                    they have been removed in the latest version
                                    of the source.
        @type keepRemovedPackages: list(nevra, nevra, ...)
        """

        if force is not None:
            self._cfg.disableUpdateSanity = True
            assert isinstance(force, list)

        if updatePkgs and not updateTroves:
            updateTroves = set(((x.name, None, None), x) for x in updatePkgs)

        start = time.time()
        log.info('starting update : %s' % start)

        if not expectedRemovals:
            ##
            # We are going to put together a list of all the removed pkgs
            # it is needed to check the group for stuff we want out
            ##

            removeObsoleted = set([ x for x in
                itertools.chain(*self._cfg.removeObsoleted.values()) ])
            updateRemovesPackage = set([ x for x in
                itertools.chain(*self._cfg.updateRemovesPackages.values()) ])

            expectedRemovals = removeObsoleted | updateRemovesPackage


        if not expectedRemovals:
            ##
            # We are going to put together a list of all the removed pkgs
            # it is needed to check the group for stuff we want out
            ##

            removeObsoleted = set([ x for x in
                itertools.chain(*self._cfg.removeObsoleted.values()) ])
            updateRemovesPackage = set([ x for x in
                itertools.chain(*self._cfg.updateRemovesPackages.values()) ])

            expectedRemovals = removeObsoleted | updateRemovesPackage


        # Populate rpm source object from yum metadata.
        self._pkgSource.load()

        # Get troves to update and send advisories.
        toAdvise, toUpdate = self._updater.getUpdates(
            updateTroves=updateTroves,
            expectedRemovals=expectedRemovals,
            allowPackageDowngrades=allowPackageDowngrades,
            keepRemovedPackages=keepRemovedPackages)

        log.info('Found %s updates : %s' % (len(toUpdate), time.time()))
 
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

        # Update source
        parentPackages = set()
        for nvf, srcPkg in toUpdate:
            toAdvise.remove((nvf, srcPkg))
            newVersion = self._updater.update(nvf, srcPkg)
            if self._updater.isPlatformTrove(newVersion):
                toAdvise.append(((nvf[0], newVersion, nvf[2]), srcPkg))
            else:
                parentPackages.add((nvf[0], newVersion, nvf[2]))

        log.info('looking up binary versions of all parent platform packages')
        parentPkgMap = self._updater.getBinaryVersions(parentPackages,
            labels=self._cfg.platformSearchPath)

        # Make sure to build everything in the toAdvise list, there may be
        # sources that have been updated, but not built.
        buildTroves = self._formatBuildTroves(toAdvise)

        # If importing specific packages, they might require each other so
        # always use buildmany, but wait to commit.
        if updatePkgs:
            trvMap, failed = self._builder.buildmany(buildTroves,
                                                     lateCommit=True)

        # Switch to splitarch if a build is larger than maxBuildSize. This
        # number is kinda arbitrary. Builds tend to break when architectures
        # are combind if the build is significantly large
        elif len(buildTroves) < self._cfg.maxBuildSize:
            trvMap = self._builder.build(buildTroves)
        else:
            trvMap = self._builder.buildsplitarch(buildTroves)

        # Updates for centos 5 unencap require grpbuild and promote
        if self._cfg.updateMode == 'latest' and self._cfg.platformName == 'centos':
            # Build group.
            log.info('Building group : %s' %  self._cfg.topSourceGroup.asString())
            grpTrvs = (self._cfg.topSourceGroup, )
            grpTrvMap = self._builder.build(grpTrvs)

            # Promote group.
            # We expect that everything that was built will be published.
            if self._cfg.targetLabel != self._cfg.sourceLabel[-1]:
                expected = self._flattenSetDict(trvMap)
                toPublish = self._flattenSetDict(grpTrvMap)
                newTroves = self._updater.publish(toPublish, expected,
                                               self._cfg.targetLabel)

            # Disabled handled in seperate job
            # Mirror out what we have done
            #self._updater.mirror()


        log.info('update completed successfully')
        log.info('updated %s packages and sent %s advisories'
                 % (len(toUpdate), len(toAdvise)))
        log.info('elapsed time %s' % (time.time() - start, ))

        # Add any platform packages to the trove map.
        trvMap.update(parentPkgMap)

        return trvMap

    def mirror(self, fullTroveSync=False):
        """
        Mirror platform contents to production repository.
        """

        return self._updater.mirror(fullTroveSync=fullTroveSync)
