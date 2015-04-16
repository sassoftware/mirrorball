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
Module for finding packages to update and updating them.
"""

import os
import time
import copy
import logging
import itertools

from rpmutils import rpmvercmp

from updatebot.lib import util
from updatebot import conaryhelper
from updatebot.errors import GroupNotFound
from updatebot.errors import NoManifestFoundError
from updatebot.errors import SourceNotImportedError
from updatebot.errors import OldVersionNotFoundError
from updatebot.errors import UpdateGoesBackwardsError
from updatebot.errors import UpdateReusesPackageError
from updatebot.errors import UpdateRemovesPackageError
from updatebot.errors import ParentPlatformManifestInconsistencyError
from updatebot.errors import RepositoryPackageSourceInconsistencyError

log = logging.getLogger('updatebot.update')

# added to deal with parent platform's lack of ?arch=
# in some manifests -- probably only needed related to bi-arch rebuilds?
import re
dropArchRE = re.compile('\?.*')

class Updater(object):
    """
    Class for finding and updating packages.
    """

    def __init__(self, cfg, ui, pkgSource):
        self._cfg = cfg
        self._ui = ui

        self._pkgSource = pkgSource

        self._conaryhelper = conaryhelper.ConaryHelper(self._cfg)

    def getUpdates(self, updateTroves=None, expectedRemovals=None,
        allowPackageDowngrades=None, keepRemovedPackages=None):
        """
        Find all packages that need updates and/or advisories from a top level
        binary group.
        @param updateTroves: set of troves to update
        @type updateTroves: iterable
        @param expectedRemovals: set of package names that are expected to be
                                 removed.
        @type expectedRemovals: set of package names
        @param allowPackageDowngrades: list of source nevra tuples to downgrade
                                       from/to.
        @type allowPackageDowngrades: list(list(from srcNevra, to srcNevra), )
        @param keepRemovedPackages: list of package nevras to keep even though
                                    they have been removed in the latest version
                                    of the source.
        @type keepRemovedPackages: list(nevra, nevra, ...)
        @return list of packages to send advisories for and list of packages
                to update
        """

        start = time.time()
        log.info('Searching for packages to update : %s' % start)

        assert updateTroves is None or len(updateTroves)

        toAdvise = []
        toUpdate = []

        # If update set is not specified get the latest versions of packages to
        # update.
        if not updateTroves:
            updateTroves = self._findUpdatableTroves(self._cfg.topGroup)

        for nvf, srpm in updateTroves:
            # Will raise exception if any errors are found, halting execution.
            if self._sanitizeTrove(nvf, srpm,
                    expectedRemovals=expectedRemovals,
                    allowPackageDowngrades=allowPackageDowngrades,
                    keepRemovedPackages=keepRemovedPackages):
                toUpdate.append((nvf, srpm))
                toAdvise.append((nvf, srpm))


            # Update versions for things that are already in the repository.
            # The binary version from the group will not be the latest.
            else:
                # Make sure to send advisories for any packages that didn't get
                # sent out last time.
                version = self._conaryhelper.getLatestSourceVersion(nvf[0])
                toAdvise.append(((nvf[0], version, nvf[2]), srpm))


        log.info('Found %s troves to update, and %s troves to send advisories'
                 % (len(toUpdate), len(toAdvise)))
        log.info('Elapsed Time : %s' % (time.time() - start))
        return toAdvise, toUpdate

    def _fltrPkg(self, pkgname):
        """
        Return True if this is a package that should be filtered out.
        """

        if (pkgname.startswith('info-') or
            pkgname.startswith('group-') or
            pkgname.startswith('factory-') or
            pkgname in self._cfg.excludePackages):
            return True

        return False

    def _findUpdatableTroves(self, group):
        """
        Query a group to find packages that need to be updated.
        @param group: package spec for the top level group to query
        @type group: (name, versionObj, flavorObj)
        @return list of nvf and src package object
        """

        # ((name, version, flavor), srpm)
        troves = []
        for name, version, flavor in \
          self._conaryhelper.getSourceTroves(group).iterkeys():
            name = name.split(':')[0]

            # skip special packages
            if self._fltrPkg(name):
                continue

            latestSrpm = self._getLatestSource(name)
            latestVer = util.srpmToConaryVersion(latestSrpm)
            curVer = str(version.trailingRevision().version)
            if rpmvercmp(latestVer, curVer) != 0:
                log.info('found potential updatable trove: %s'
                         % ((name, version, flavor), ))
                log.debug('cny: %s, rpm: %s' % (curVer, latestVer))
                # Add anything that has changed, version may have gone
                # backwards if epoch changes.
                troves.append(((name, version, flavor), latestSrpm))

        log.info('found %s protentially updatable troves' % len(troves))
        return troves

    def getSourceVersions(self):
        """
        Query the repository for a list of latest source trove specs and
        matching binaries.
        @return {srcTroveSpec: set(binTrovSpec, ...)}
        """

        # Get the latest versions from repository
        troves = self._conaryhelper._getLatestTroves()

        # Convert to a n, v, f list excluding components and sources.
        troveSpecs = []
        for name, verDict in troves.iteritems():
            if ':' in name:
                continue
            assert len(verDict) == 1
            version = verDict.keys()[0]
            flavor = list(verDict[version])[0]
            troveSpecs.append((name, version, flavor))

        # Get the sources for all binary packages.
        sourceVersions = self._conaryhelper.getSourceVersions(troveSpecs)

        return sourceVersions

    def getSourceVersionMap(self):
        """
        Query the repository for a list of the latest source names and versions
        that have binary versions.
        @return {sourceName: sourceVersion}
        """

        sourceVersions = self.getSourceVersions()

        # Convert to sourceName: version map.
        return dict([ (x.split(':')[0], y)
                      for x, y, z in sourceVersions.iterkeys()
                      if not self._fltrPkg(x.split(':')[0])
                    ])

    def getBinaryVersions(self, srcTrvSpecs, labels=None):
        """
        Find the latest version of all binaries built from the specified
        sources.
        @param srcTroveSpecs: list of source troves.
        @type srcTroveSpecs: [(name, versionObj, None), ... ]
        @param labels: list of labels to search, defaults to the buildLabel
        @type labels: list(conary.versions.Label, ...)
        @return {srcTrvSpec: [binTrvSpec, binTrvSpec, ... ]}
        """

        # Short circuit trove caching if trove list is empty.
        if not srcTrvSpecs:
            return {}

        # Make sure all sources end in :source
        req = []
        for n, v, f in srcTrvSpecs:
            if not n.endswith(':source'):
                n = '%s:source' % n
            req.append((n, v, f))

        return self._conaryhelper.getBinaryVersions(req, labels=labels)

    def getSourceVersionMapFromBinaryVersion(self, (n, v, f), labels=None,
        latest=False, includeBuildLabel=False):
        """
        Find a mapping of source to binaries, given a single binary name,
        version, and flavor.
        @param nvf: binary name, version, and flavor
        @type nvf: tuple(name, versionObj, falvorObj)
        @param labels: list of labels to search, defaults to buildLabel
        @type labels: list(conary.versions.Label, ...)
        @param latest: check for only the latest versions or not
        @type latest: boolean
        @return {srcTrvSpec: [binTrvSpec, binTrvSpec, ...]}
        """

        return self._conaryhelper.getSourceVersionMapFromBinaryVersion(
            (n, v, f), labels=labels, latest=latest,
            includeBuildLabel=includeBuildLabel)

    def getBinaryVersionsFromSourcePackage(self, srcPkg):
        """
        Get a list of all packages in the conary repository that were built from
        the given source package.
        @param srcPkg: source package object
        @type srcPkg: repomd.packagexml._Package
        @return set of binary trove specs
        @rtype set([(str, conary.versions.Version, conary.deps.deps.Flavor), ])
        """

        binMap = self.getBinaryVersionsFromSourcePackages((srcPkg, ))
        assert srcPkg in binMap
        assert binMap[srcPkg]
        return binMap[srcPkg]

    def getBinaryVersionsFromSourcePackages(self, srcPkgs):
        """
        Get a list of all packages in the conary repository that were built from
        the given source package.
        @param srcPkgs: itertable of source package objects
        @type srcPkgs: list(repomd.packagexml._Package, ...)
        @return dict of set of binary trove specs
        @rtype dict((repomd.packagexml._Package,
               set([(str, conary.versions.Version, conary.deps.deps.Flavor), ]))
        """

        labels = copy.copy(self._cfg.platformSearchPath) or list()
        labels.insert(0, self._conaryhelper.getConaryConfig().buildLabel)

        # Find the conary source troves
        sources = dict([ (('%s:source' % x.name, x.getConaryVersion(), None), x)
                        for x in srcPkgs ])
        srcTrvMap = self._conaryhelper.findTroves(sources.keys(), labels=labels,
            getLeaves=False)

        srcTrvs = {}
        for src, cSrcs in srcTrvMap.iteritems():
            srcPkg = sources[src]
            for n, v, f in cSrcs:
                srcTrvs[(n, v, None)] = srcPkg

        # Get a mapping of binaries
        srcMap = self._conaryhelper.getBinaryVersions(srcTrvs.keys(),
            labels=labels, latest=False, missingOk=True)

        # Return binary versions
        bins = [ x for x in itertools.chain(*srcMap.itervalues()) ]

        binMap = {}
        for srcTrv, binaries in srcMap.iteritems():
            assert binaries
            binMap.setdefault(srcTrvs[srcTrv], set()).update(set(binaries))

        return binMap

    def getTargetVersions(self, binTrvSpecs, logErrors=True):
        """
        Given a list of binary trove specs from the devel label return a list of
        promoted trove versions.
        """

        cfMap = self._conaryhelper.getClonedFromForLabel(self._cfg.targetLabel)
        failed = []
        targetSpecs = []
        for spec in binTrvSpecs:
            if spec not in cfMap:
                failed.append(spec)
            else:
                targetSpecs.append(cfMap[spec])

        seen = [ (x, y.getSourceVersion())
                 for x, y, z in binTrvSpecs
                 if (x, y, z) not in failed ]

        fail = [ (x, y, z)
                 for x, y, z in failed
                 if (x, y.getSourceVersion()) not in seen ]

        if logErrors:
            for spec in fail:
                log.critical('%s=%s[%s] not found in cloned from map' % spec)

        return targetSpecs, fail

    def _getLatestSource(self, name):
        """
        Get the latest src package for a given package name.
        @param name: name of the package to retrieve
        @type name: string
        @return src package object
        """

        srpms = list(self._pkgSource.srcNameMap[name])
        srpms.sort(util.packagevercmp)
        return srpms[-1]

    def _sanitizeTrove(self, nvf, srpm, expectedRemovals=None,
        allowPackageDowngrades=None, keepRemovedPackages=None):
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
        @param expectedRemovals: set of package names that are expected to be
                                 removed.
        @type expectedRemovals: set of package names
        @param allowPackageDowngrades: list of source nevra tuples to downgrade
                                       from/to.
        @type allowPackageDowngrades: list(list(from srcNevra, to srcNevra), )
        @param keepRemovedPackages: list of package nevras to keep even though
                                    they have been removed in the latest version
                                    of the source.
        @type keepRemovedPackages: list(nevra, nevra, ...)
        @return needsUpdate boolean
        @raises UpdateGoesBackwardsError
        @raises UpdateRemovesPackageError
        """

        start = time.time()
        log.info('Starting Sanitize Trove : %s' % start)

        keepRemovedPackages = keepRemovedPackages or []
        needsUpdate = False
        newNames = [ (x.name, x.arch) for x in self._pkgSource.srcPkgMap[srpm] ]
        metadata = None
        removedPackages = set()
        reusedPackages = set()

        if allowPackageDowngrades is None:
            allowPackageDowngrades = ()

        # HACK HACK HACK REMOVE ME
        if (self._cfg.targetLabel and
            'rhel-5-client-workstation' in self._cfg.targetLabel.asString()):
            log.warn('rhel-5-client found for %s, will create package' % nvf[0])
            return True
        # HACK HACK HACK END

        try:
            manifest = self._conaryhelper.getManifest(nvf[0], version=nvf[1])
        except NoManifestFoundError, e:
            # Create packages that do not have manifests.
            # TODO: might want to make this a config option?
            log.info('no manifest found for %s, will create package' % nvf[0])
            return True


        for line in manifest:
            # Some manifests were created with double slashes, need to
            # normalize the path to work around this problem.
            line = os.path.normpath(line).split('?')[0]
            if line in self._pkgSource.locationMap:
                binPkg = self._pkgSource.locationMap[line]
                srcPkg = self._pkgSource.binPkgMap[binPkg]
            elif (line.strip().endswith('.src.rpm') and
                  self._cfg.synthesizeSources):
                log.info("This is a fake source %s" % line)
                # this is a fake source.  Move on.
                continue
            elif self._cfg.disableOldVersionCheck:
                # For epel support since the repo does not
                # keep old versions at all.
                log.warn("Disabled OldVersionNotFoundError in config")
                continue
            else:
                if metadata is None:
                    pkgs = self._getMetadataFromConaryRepository(nvf[0],
                                                                 version=nvf[1])
                    if pkgs:
                        metadata = util.Metadata(pkgs)
                    if metadata:
                        binPkg = metadata.locationMap[line]
                        srcPkg = metadata.binPkgMap[binPkg]
                    else:
                        raise OldVersionNotFoundError(
                            why="can't find metadata for %s" % line)

            # set needsUpdate if version changes
            if util.packagevercmp(srpm, srcPkg) == 1:
                needsUpdate = True

            # make sure new package is actually newer
            if util.packagevercmp(srpm, srcPkg) == -1:
                # In current mode we just need to build
                # attempts are made in update set to keep the latest rpm
                # the latest conary version so just let it go
                if self._cfg.updateMode == 'current':
                    srcTuple = (srcPkg.getNevra(), srpm.getNevra())
                    log.warn('running in current mode ignoring')
                    log.warn('version goes backwards %s -> %s' % srcTuple)
                    needsUpdate = True
                else:
                    srcTuple = (srcPkg.getNevra(), srpm.getNevra())
                    log.warn('version goes backwards %s -> %s' % srcTuple)
                    if srcTuple in allowPackageDowngrades:
                        log.info('found version downgrade exception in '
                             'configuration')
                        needsUpdate = True
                    else:
                        raise UpdateGoesBackwardsError(why=(srcPkg, srpm))

            # make sure we aren't trying to remove a package
            if ((binPkg.name, binPkg.arch) not in newNames and
                not self._cfg.disableUpdateSanity):
                # Novell releases updates to only the binary rpms of a package
                # that have chnaged. We have to use binaries from the old srpm.
                # Get the last version of the pkg and add it to the srcPkgMap.
                pkgs = sorted([
                    x for x in self._pkgSource.binNameMap[binPkg.name]
                        if x.arch == binPkg.arch ])

                # Maybe this is a src or nosrc.
                if not pkgs:
                    pkgs = sorted([
                        x for x in self._pkgSource.srcNameMap[binPkg.name]
                        if x.arch == binPkg.arch ])

                # If running in latest mode we really want to compare to the
                # latest version of this binary, but if we are running in
                # ordered we really want the "next" version of this binary.
                pkg = None
                if self._cfg.updateMode == 'latest':
                    # get the correct arch
                    latestPkgs = self._getLatestOfAvailableArches(pkgs)
                    assert latestPkgs
                    pkg = latestPkgs[0]

                elif self._cfg.updateMode == 'current':
                    # for current mode we are using this method
                    # get the correct arch
                    latestPkgs = self._getLatestOfAvailableArches(pkgs)
                    assert latestPkgs
                    pkg = latestPkgs[0]

                elif self._cfg.updateMode == 'ordered':
                    idx = pkgs.index(binPkg)
                    if len(pkgs) - 1 > idx:
                        pkg = pkgs[idx+1]
                    else:
                        # This means that this package has no newer versions.
                        log.info('no newer version of %s found' % binPkg.name)

                # Get the source that the package was built from for version
                # comparison since the source and binary can have different
                # versions.
                if pkg:
                    src = self._pkgSource.binPkgMap[pkg]
                else:
                    src = srcPkg

                # Raise an exception if the versions of the packages aren't
                # equal or the discovered package comes from a different source.
                if (rpmvercmp(src.epoch, srpm.epoch) != 0 or
                    rpmvercmp(src.version, srpm.version) != 0 or
                    # in the suse case we have to ignore release
                    (not self._cfg.reuseOldRevisions and
                     rpmvercmp(src.release, srpm.release) != 0) or
                    # binary does not come from the same source as it used to
                    src.name != srpm.name):
                    log.warn('update removes package (%s) %s -> %s'
                            % (binPkg.name, srcPkg.getNevra(), srpm.getNevra()))

                    # allow some packages to be removed.
                    if expectedRemovals and binPkg.name in expectedRemovals:
                        log.info('package removal (%s) handled in configuration'
                                 % binPkg.name)
                        continue

                    if binPkg.getNevra() not in keepRemovedPackages:
                        removedPackages.add(binPkg)

                if not removedPackages:
                    if binPkg.getNevra() not in keepRemovedPackages:
                        reusedPackages.add(binPkg)
                    log.warn('using old version of package %s' % (binPkg, ))
                    self._pkgSource.srcPkgMap[srpm].add(binPkg)

        if removedPackages and not self._cfg.allowRemovedPackages:
            pkgList=sorted(removedPackages)
            raise UpdateRemovesPackageError(pkgList=pkgList,
                pkgNames=' '.join([str(x) for x in pkgList]),
                newspkg=srpm, oldspkg=srcPkg,
                oldNevra=str(' '.join(srcPkg.getNevra())),
                newNevra=str(' '.join(srpm.getNevra())))

        if reusedPackages and not self._cfg.reuseOldRevisions:
            pkgList=sorted(reusedPackages)
            raise UpdateReusesPackageError(pkgList=pkgList,
                pkgNames=' '.join([str(x) for x in pkgList]),
                newspkg=srpm, oldspkg=srcPkg,
                oldNevra=str(' '.join(srcPkg.getNevra())),
                newNevra=str(' '.join(srpm.getNevra())))

        if len(manifest) < self._getManifestFromPkgSource(srpm):
            needsUpdate = True

        log.debug('Elapsed Time Sanitize Trove : %s' % (time.time() - start))

        return needsUpdate

    def sanityCheckSource(self, srpm, allowPackageDowngrades=None):
        """
        Look up the matching source version in the conary repository and verify
        that the manifest matches the package list in the package source.
        @param srpm: src pacakge object
        @type srpm: repomd.packagexml._Package
        @param allowPackageDowngrades: list of source nevra tuples to downgrade
                                       from/to.
        @type allowPackageDowngrades: list(list(from srcNevra, to srcNevra), )
        """

        srcQuery = ('%s:source' % srpm.name, srpm.getConaryVersion(), None)
        nvflst = self._conaryhelper.findTrove(srcQuery)

        # If this package was not found on the platform label, check if there
        # are parent platforms involved.
        if not nvflst and self._cfg.platformSearchPath:
            nvflst = self._conaryhelper.findTrove(srcQuery,
                labels=self._cfg.platformSearchPath)

            # Trust that the parent platform has sanity checked this source.
            if nvflst:
                return None

        # Source hasn't been imported.
        if not nvflst:
            log.error('source has not been imported: %s' % srpm)
            raise SourceNotImportedError(srpm=srpm)

        assert len(nvflst) == 1
        n, v, f = nvflst[0]
        nvf = (n.split(':')[0], v, None)

        needsUpdate = self._sanitizeTrove(nvf, srpm,
            allowPackageDowngrades=allowPackageDowngrades)

        # If anything has chnaged raise an error.
        if needsUpdate:
            raise RepositoryPackageSourceInconsistencyError(nvf=nvf, srpm=srpm)

    def _getLatestOfAvailableArches(self, pkgLst):
        """
        Given a list of package objects, find the latest versions of each
        package for each name/arch.
        @param pkgLst: list of packages
        @type pkgLst: [repomd.packagexml._Package, ...]
        """

        pkgLst.sort()

        pkgMap = {}
        for pkg in pkgLst:
            arch = self._getRepositoryArch(pkg.location)
            key = pkg.name + pkg.arch + arch
            if key not in pkgMap:
                pkgMap[key] = pkg
                continue

            # check if newer, first wins
            if util.packagevercmp(pkg, pkgMap[key]) in (1, ):
                pkgMap[key] = pkg

        ret = pkgMap.values()
        ret.sort()

        return ret

    def create(self, pkgNames=None, buildAll=False, recreate=False,
               toCreate=None):
        """
        Import a new package into the repository.
        @param pkgNames: list of packages to import
        @type pkgNames: list
        @param buildAll: return a list of all troves found rather than just the
                         new ones.
        @type buildAll: boolean
        @param recreate: a package manifest even if it already exists.
        @type recreate: boolean
        @return new source [(name, version, flavor), ... ]

        @param toCreate: set of packages to update. If this is set all other
                         options are ignored.
        @type toCreate: set of source package objects.
        """

        assert pkgNames or toCreate

        if pkgNames:
            toCreate = set()
        else:
            # Import very specific versions of packages.
            pkgNames = []
            recreate = False

        log.info('getting existing packages')
        pkgs = self._getExistingPackageNames()

        # Find all of the source to update.
        for pkg in pkgNames:
            if pkg not in self._pkgSource.binNameMap:
                log.warn('no package named %s found in package source' % pkg)
                continue

            srcPkg = self._getPackagesToImport(pkg)

            if srcPkg.name not in pkgs or recreate:
                toCreate.add(srcPkg)

        verCache = self._conaryhelper.getLatestVersions()
        # In the case that we are rebuilding and already have groups available,
        # try to only build packages that have not been rebuilt.
        if buildAll and pkgs and not pkgNames:
            nv = {}
            for sn, pkgs in pkgs.iteritems():
                for n, v, f in pkgs:
                    if n not in nv:
                        nv[n] = (v, sn)

            create = set()
            toCreateMap = dict([ (x.name, x) for x in toCreate ])
            for n, v in verCache.iteritems():
                # Skip all components, including sources
                if len(n.split(':')) > 1:
                    continue
                # If binary is in the group and the version on the label is the
                # same it needs to be updated.
                if n in nv and v == nv[n][0] and nv[n][1] in toCreateMap:
                    create.add(toCreateMap[nv[n][1]])

            toCreate = create

        # Update all of the unique sources.
        fail = set()
        toBuild = set()
        preBuiltPackages = set()
        parentPackages = set()
        total = len(toCreate)
        current = 1

        for pkg in sorted(toCreate):
            try:
                # Only import packages that haven't been imported before
                version = verCache.get('%s:source' % pkg.name)
                if not version or recreate:
                    log.info('attempting to import %s (%s/%s)'
                             % (pkg, current, total))
                    version = self.update((pkg.name, None, None), pkg)

                if (not verCache.get(pkg.name) or
                    verCache.get(pkg.name).getSourceVersion() != version or
                    buildAll or recreate):

                    if self.isPlatformTrove(version):
                        toBuild.add(((pkg.name, version, None), pkg))
                    else:
                        parentPackages.add((pkg.name, version, None))
                else:
                    log.info('not building %s' % pkg.name)
                    preBuiltPackages.add((pkg.name, version, None))
            except Exception, e:
                log.error('failed to import %s: %s' % (pkg, e))
                fail.add((pkg, e))
            current += 1

        if buildAll and pkgs and pkgNames:
            toBuild.update(
                [ ((x, self._conaryhelper.getLatestSourceVersion(x), None),
                   None)
                  for x in pkgs if not self._fltrPkg(x) ]
            )

        # Handle parent packages if we are a child platform.
        pkgMap = {}
        if parentPackages:
            # Find all of the binaries that match the upstream platform sources.
            log.info('looking up binary versions of all parent platform '
                     'packages')
            parentPkgMap = self.getBinaryVersions(parentPackages,
                labels=self._cfg.platformSearchPath)

            # Find all of the binaries that match the pre-built sources.
            log.info('looking up binary version information for all prebuilt '
                     'packages')
            preBuiltPackageMap = self.getBinaryVersions(preBuiltPackages)

            # Combine the two package maps by name where pre built packages
            # override parent packages.
            parentNames = dict([ (x[0], x) for x in parentPkgMap ])
            preBuiltNames = dict([ (x[0], x) for x in preBuiltPackageMap ])

            parentNames.update(preBuiltNames)
            parentPkgMap.update(preBuiltPackageMap)

            pkgMap = dict([ (parentNames[x], parentPkgMap[parentNames[x]])
                            for x in parentNames ])

        return toBuild, pkgMap, fail

    def _getExistingPackageNames(self):
        """
        Returns a list of names of all sources included in the top level group.
        """

        # W0612 - Unused variable
        # pylint: disable=W0612

        try:
            return dict([(n.split(':')[0], pkgs) for (n, v, f), pkgs in
            self._conaryhelper.getSourceTroves(self._cfg.topGroup).iteritems()])
        except GroupNotFound:
            return {}

    def _getPackagesToImport(self, name):
        """
        Add any missing packages to the srcPkgMap entry for this package.
        @param name: name of the srpm to look for.
        @type name: string
        @return latest source package for the given name
        """

        latestRpm = self._getLatestBinary(name)
        latestSrpm = self._pkgSource.binPkgMap[latestRpm]

        pkgs = {}
        pkgNames = set()
        for pkg in self._pkgSource.srcPkgMap[latestSrpm]:
            pkgNames.add(pkg.name)
            pkgs[(pkg.name, pkg.arch)] = pkg

        for srpm in self._pkgSource.srcNameMap[latestSrpm.name]:
            if latestSrpm.epoch == srpm.epoch and \
               latestSrpm.version == srpm.version:
                for pkg in self._pkgSource.srcPkgMap[srpm]:
                    # Add special handling for packages that have versions in
                    # the names.
                    # FIXME: This is specific to non rpm based platforms right
                    #        now. It needs to be tested on rpm platforms to
                    #        make nothing breaks.
                    if (self._cfg.repositoryFormat != 'rpm'
                        and pkg.name not in pkgNames
                        and pkg.version in pkg.name):
                        continue
                    if (pkg.name, pkg.arch) not in pkgs:
                        pkgs[(pkg.name, pkg.arch)] = pkg

        self._pkgSource.srcPkgMap[latestSrpm] = set(pkgs.values())

        return latestSrpm

    def _getLatestBinary(self, name):
        """
        Find the latest version of a given binary package.
        @param name: name of the package to look for
        @type name: string
        """

        rpms = list(self._pkgSource.binNameMap[name])
        rpms.sort(util.packagevercmp)
        return rpms[-1]

    def update(self, nvf, srcPkg):
        """
        Update rpm manifest in source trove.
        @param nvf: name, version, flavor tuple of source trove
        @type nvf: tuple(name, versionObj, flavorObj)
        @param srcPkg: package object for source rpm
        @type srcPkg: repomd.packagexml._Package
        @return version of the updated source trove
        """

        # Try to use package from a parent platform if the manifests match,
        # unless there is already a version on the platform label.
        parentVersion = self._getUpstreamPackageVersion(nvf, srcPkg)
        if parentVersion:
            log.info('using version from parent platform %s' % parentVersion)
            return parentVersion

        # artifactory packages use a completely
        # different manifest format
        if self._cfg.repositoryFormat == 'artifactory':
            manifest = dict(
                version=srcPkg.version,
                build_requires=srcPkg.buildRequires,
                artifacts=srcPkg.artifacts,
            )
            self._conaryhelper.setJsonManifest(nvf[0], manifest)
        else:
            manifest = self._getManifestFromPkgSource(srcPkg)
            self._conaryhelper.setManifest(nvf[0], manifest)

        if self._cfg.writePackageVersion:
            self._conaryhelper.setVersion(nvf[0], '%s_%s'
                % (srcPkg.version, srcPkg.release))

        # FIXME: This is apt specific for now. Once repomd has been rewritten
        #        to use something other than rpath-xmllib we should be able to
        #        convert this to xobj.
        if (self._cfg.repositoryFormat == 'apt' or
            self._cfg.writePackageMetadata):
            metadata = self._getMetadataFromPkgSource(srcPkg)
            self._conaryhelper.setMetadata(nvf[0], metadata)

        if self._cfg.repositoryFormat == 'yum' and self._cfg.buildFromSource:
            buildrequires = self._getBuildRequiresFromPkgSource(srcPkg)
            self._conaryhelper.setBuildRequires(nvf[0], buildrequires)

        newVersion = self._conaryhelper.commit(nvf[0],
                                    commitMessage=self._cfg.commitMessage)
        return newVersion

    def _getUpstreamPackageVersion(self, nvf, srcPkg):
        """
        Check if a package is maintained as part of an upstream platform.
        @param nvf: name, version, flavor tuple of source trove
        @type nvf: tuple(name, versionObj, flavorObj)
        @param srcPkg: package object for source rpm
        @type srcPkg: repomd.packagexml._Package
        """

        # If there is no parent platform search path definied, don't
        # bother looking.
        if not self._cfg.platformSearchPath:
            return None

        srcName = '%s:source' % nvf[0]

        # Check if this package is maintained as part of the current platform.
        hasName = self._conaryhelper.findTrove((srcName, None, None))

        # This is an existing source on the child label
        if hasName:
            return None

        # Search for source upstream
        srcSpec = (srcName, srcPkg.getConaryVersion(), None)
        srcTrvs = self._conaryhelper.findTrove(srcSpec,
            labels=self._cfg.platformSearchPath)

        # This is a new package on the child label
        if not srcTrvs:
            return None

        assert len(srcTrvs) == 1
        srcVersion = srcTrvs[0][1]

        manifest = self._getManifestFromPkgSource(srcPkg)
        parentManifest = self._conaryhelper.getManifest(nvf[0],
                                                        version=srcVersion)

        # FIXME: This assumes that if the rpm filenames are the same the rpm
        #        contents are the same.

        # Take the basename of all paths in the manifest since the same rpm will
        # be in different repositories for each platform.
        baseManifest = sorted([ dropArchRE.sub('', os.path.basename(x))
            for x in manifest ])
        parentBaseManifest = sorted([ dropArchRE.sub('', os.path.basename(x))
                                      for x in parentManifest ])
        # baseManifest = sorted([ os.path.basename(x) for x in manifest ])
        # parentBaseManifest = sorted([ os.path.basename(x)
        #                               for x in parentManifest ])

        if baseManifest != parentBaseManifest:
            if (srcPkg.getFileName() in
                self._cfg.expectParentManifestDifferences):

                if (srcPkg.getFileName() in baseManifest and
                    srcPkg.getFileName() in parentBaseManifest):

                    log.info('%s: found expected difference in manifests '
                        'between parent and child platforms, ignoring parent '
                        'platform' % srcPkg)
                    return None
                else:
                    # This is basically an assertion.
                    log.error('%s: unexpected manifest error between parent '
                        'and child platforms: %s not found in both manifests'
                        % (srcName, srcPkg))
                    raise ParentPlatformManifestInconsistencyError(
                        srcPkg=srcPkg, manifest=manifest,
                        parentManifest=parentManifest)

            if self._cfg.ignoreAllParentManifestDifferences:
                log.warn('%s: found matching parent trove, but manifests '
                    'differ; soldiering onward to madness--thank goodness this '
                    'is a dry run...' % srcPkg)
                import epdb ; epdb.st()
                return None
            else:
                log.error('%s: found matching parent trove, but manifests '
                    'differ' % srcPkg)
                raise ParentPlatformManifestInconsistencyError(srcPkg=srcPkg,
                    manifest=manifest, parentManifest=parentManifest)

        return srcVersion

    def _getRepositoryArch(self, loc):
        """
        Get the architecture of the repository for a given location if
        repository arch is defined.
        """

        for repo, arch in self._cfg.repositoryArch.iteritems():
            if loc.startswith(repo):
                return arch

        return ''

    def _getManifestFromPkgSource(self, srcPkg):
        """
        Get the contents of the a manifest file from the pkgSource object.
        @param srcPkg: source rpm package object
        @type srcPkg: repomd.packagexml._Package
        """

        manifest = []

        if self._cfg.repositoryFormat == 'yum' and self._cfg.buildFromSource:
            manifest.append(srcPkg.location)
        else:
            manifestPkgs = list(self._pkgSource.srcPkgMap[srcPkg])
            for pkg in self._getLatestOfAvailableArches(manifestPkgs):
                arch = self._getRepositoryArch(pkg.location)
                location = pkg.location
                if arch:
                    location += '?arch=%s' % arch
                manifest.append(location)
        return manifest

    def getPackageFileNames(self, srcPkg):
        """
        Get the list of package names with arch flags attached.
        @param srcPkg: source rpm package object
        @type srcPkg: repomd.packagexml._Package
        """

        return [ os.path.basename(x)
                 for x in self._getManifestFromPkgSource(srcPkg) ]

    def _getMetadataFromPkgSource(self, srcPkg):
        """
        Get the data to go into the xml metadata from a srcPkg.
        @param srcPkg: source package object
        @return list of packages
        """

        return self._pkgSource.srcPkgMap[srcPkg]

    def _getMetadataFromConaryRepository(self, pkgName, version=None):
        """
        Get the metadata from the repository and generate required mappings.
        @param pkgName: source package name
        @type pkgName: string
        @param version optional source version to checkout.
        @type version conary.versions.Version
        @return dictionary of infomation that looks like a pkgsource.
        """

        return self._conaryhelper.getMetadata(pkgName, version=version)

    def _getBuildRequiresFromPkgSource(self, srcPkg):
        """
        Get the buildrequires for a given srcPkg.
        @param srcPkg: source package object
        @return list of build requires
        """

        reqs = []
        for reqType in srcPkg.format:
            if reqType.getName() == 'rpm:requires':
                names = [ x.name.split('(')[0] for x in reqType.iterChildren()
                          if not (hasattr(x, 'isspace') and x.isspace()) ]

                for name in names:
                    if name in self._pkgSource.binNameMap:
                        latest = self._getLatestBinary(name)
                        if latest not in self._pkgSource.binPkgMap:
                            log.warn('%s not found in binPkgMap' % latest)
                            continue
                        src = self._pkgSource.binPkgMap[latest]
                        srcname = src.name
                    else:
                        log.warn('found virtual requires %s in pkg %s'
                                 % (name, srcPkg.name))
                        srcname = 'virtual'
                    reqs.append((name, srcname))

        reqs = list(set(reqs))
        return reqs

    def _getBuildRequiresFromConaryRepository(self, pkgName):
        """
        Get the contents of the build requires file from the repository.
        @param pkgName: name of the package
        @type pkgName: string
        @return list of build requires
        """

        return self._conaryhelper.getBuildRequires(pkgName)

    def publish(self, trvLst, expected, targetLabel, checkPackageList=True,
        extraExpectedPromoteTroves=None, enforceAllExpected=True):
        """
        Publish a group and its contents to a target label.
        @param trvLst: list of troves to publish
        @type trvLst: [(name, version, flavor), ... ]
        @param expected: list of troves that are expected to be published.
        @type expected: [(name, version, flavor), ...]
        @param targetLabel: table to publish to
        @type targetLabel: conary Label object
        @param checkPackageList: verify list of packages being promoted or not.
        @type checkPackageList: boolean
        @param extraExpectedPromoteTroves: list of trove nvfs that are expected
                                           to be promoted, but are only filtered
                                           by name, rather than version and
                                           flavor.
        @type extraExpectedPromoteTroves: list of name, version, flavor tuples
                                          where version and flavor may be None.
        """

        return self._conaryhelper.promote(
            trvLst,
            expected,
            self._cfg.sourceLabel,
            targetLabel,
            checkPackageList=checkPackageList,
            extraPromoteTroves=self._cfg.extraPromoteTroves,
            extraExpectedPromoteTroves=extraExpectedPromoteTroves,
            enforceAllExpected=enforceAllExpected,
        )

    def mirror(self, fullTroveSync=False):
        """
        If a mirror is configured, mirror out any changes.
        """

        return self._conaryhelper.mirror(fullTroveSync=fullTroveSync)

    def setTroveMetadata(self, srcTrvSpec, binTrvSet):
        """
        Add metadata from a pkgsource to the specified troves.
        @param srcTrvSpec: source to use to find srcPkg
        @type srcTrvSpec: (name:source, conary.versions.Version, None)
        @param binTrvSet: set of binaries built from the given source.
        @type binTrvSet: set((n, v, f), ...)
        """

        srcName = srcTrvSpec[0].split(':')[0]
        srcPkg = self._getLatestSource(srcName)

        trvSpecs = list(binTrvSet)

        self._conaryhelper.setTroveMetadata(trvSpecs,
            license=srcPkg.license,
            desc=srcPkg.description,
            shortDesc=srcPkg.summary,
        )

    def isPlatformTrove(self, version):
        """
        Check if the version is on the platform label.
        @param version: version of a trove
        @type version: versionObj
        @return True if the version part is on the build label
        @rtype boolean
        """

        return self._conaryhelper.isOnBuildLabel(version)

    def getUpstreamVersionMap(self, trvSpec, latest=True):
        """
        Get a mapping of all binary versions in the repository that match
        the specified trove spec, keyed by upstream version.
        @param trvSpec: trove tuple of name, version, and flavor
        @type trvSpec: tuple(str, str, str)
        @param latest: return only the latest versions of each upstream version.
        @type latest: boolean
        @return map of upstream version to nvfs
        @rtype dict(revision=[(str, conary.versions.Version,
                                    conary.deps.deps.Flavor), ...])
        """

        # get the mapping of source spec to binary spec.
        srcMap = self.getSourceVersionMapFromTroveSpec(trvSpec)

        # If not requesting latest versions, go ahead and return mapping of
        # upstream versions to binary versions.
        if not latest:
            return dict([ (x[1].trailingRevision().getVersion(), y)
                          for x, y in srcMap.iteritems() ])

        # Build a mapping for version filtering.
        upverMap = {}
        for src, bins in srcMap.iteritems():
            upver = src[1].trailingRevision().getVersion()
            vMap = upverMap.setdefault(upver, dict())
            for n, v, f in bins:
                vMap.setdefault(v, set()).add((n, v, f))

        # Filter out the latest versions.
        latestMap = {}
        for upver, vMap in upverMap.iteritems():
            recent = None
            for v, nvfs in vMap.iteritems():
                if recent is None:
                    recent = v
                    continue
                if recent < v:
                    recent = v

            # Store the latest versions that we need to promote
            assert upver not in latestMap
            latestMap[upver] = vMap[recent]

        return latestMap

    def getSourceVersionMapFromTroveSpec(self, trvSpec):
        """
        Get a mapping of source to binary versions for all troves matching the
        specified trove spec.
        @param trvSpec: trove tuple of name, version, and flavor
        @type trvSpec: tuple(str, str, str)
        @return map of source trove to binary troves
        @rtype dict((str, conary.versions.Version, None)=[(str,
            conary.versions.Version, conary.deps.deps.Flavor), ...])
        """

        if not trvSpec[0].endswith(':source'):
            srcSpec = ('%s:source' % trvSpec[0], trvSpec[1], None)
        else:
            srcSpec = (trvSpec[0], trvSpec[1], None)

        srcTrvs = self._conaryhelper.findTrove(srcSpec, getLeaves=False)

        if not srcTrvs:
            log.warn('no versions of %s found on %s' % (srcSpec[0], srcSpec[1]))
            return {}

        filteredSrcTrvs = [ (x, y, None) for x, y, z in srcTrvs ]
        assert filteredSrcTrvs
        srcMap = self._conaryhelper.getBinaryVersions(filteredSrcTrvs,
            missingOk=True, labels=[filteredSrcTrvs[0][1].trailingLabel(), ])
        return srcMap

    def getSourceVersionMapFromSrpms(self, srpms):
        """
        Generate a mapping of source trove tuple to binary trove tuple for all
        source rpms in srpms.
        @param srpms: collection of srpm objects.
        @return dict((str, conary.versions.Version, None)=[(str,
            conary.versions.Version, conary.deps.deps.Flavor), ...])
        """

        query = [ ('%s:source' % x.name, x.getConaryVersion(), None)
            for x in srpms ]
        results = self._conaryhelper.findTroves(query, allowMissing=True)
        srcSpecs = [ x for x in itertools.chain(*results.itervalues()) ]
        labels = list(set([ x[1].trailingLabel() for x in srcSpecs ]))
        pkgMap = self._conaryhelper.getBinaryVersions(srcSpecs, missingOk=True,
            labels=labels)

        return pkgMap

    def remove(self, srcPkgs):
        """
        Remove all instances of packages from the conary repository that were
        generated by a given source package.
        @param srcPkgs: list of source package objects.
        @type srcPkgs: list(repomd.packagexml._Package, ...)
        @return list of trove specs that have been removed.
        @rtype list((str, conary.versions.VersionFromString,
                          conary.deps.deps.Flavor), ...)
        """

        trvSpecs = [ ('%s:source' % x.name, x.getConaryVersion(), None)
                     for x in srcPkgs ]

        removeSpecs, cs = self._conaryhelper.markremoved(trvSpecs,
            removeSources=True, removeSiblings=True, removeAllVersions=False)

        for spec in sorted(removeSpecs):
            log.info('removing: %s=%s[%s]' % spec)

        log.info('total troves to remove: %s' % len(removeSpecs))

        commit = True
        if self._ui.cfg.interactive:
            commit = self._ui.ask('remove troves?', default=False)

        if commit:
            log.info('committing')
            self._conaryhelper._repos.commitChangeSet(cs)
            log.info('committed')

        return removeSpecs
