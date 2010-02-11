#
# Copyright (c) 2008-2010 rPath, Inc.
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

import os
import logging

from rpmutils import rpmvercmp

from updatebot.lib import util
from updatebot import conaryhelper
from updatebot.errors import GroupNotFound
from updatebot.errors import NoManifestFoundError
from updatebot.errors import OldVersionNotFoundError
from updatebot.errors import UpdateGoesBackwardsError
from updatebot.errors import UpdateRemovesPackageError
from updatebot.errors import ParentPlatformManifestInconsistencyError

log = logging.getLogger('updatebot.update')

class Updater(object):
    """
    Class for finding and updating packages.
    """

    def __init__(self, cfg, pkgSource):
        self._cfg = cfg
        self._pkgSource = pkgSource

        self._conaryhelper = conaryhelper.ConaryHelper(self._cfg)

    def getUpdates(self, updateTroves=None, expectedRemovals=None):
        """
        Find all packages that need updates and/or advisories from a top level
        binary group.
        @param updateTroves: set of troves to update
        @type updateTroves: iterable
        @param expectedRemovals: set of package names that are expected to be
                                 removed.
        @type expectedRemovals: set of package names
        @return list of packages to send advisories for and list of packages
                to update
        """

        log.info('searching for packages to update')

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
                                   expectedRemovals=expectedRemovals):
                toUpdate.append((nvf, srpm))
                toAdvise.append((nvf, srpm))


            # Update versions for things that are already in the repository.
            # The binary version from the group will not be the latest.
            else:
                # Make sure to send advisories for any packages that didn't get
                # sent out last time.
                version = self._conaryhelper.getLatestSourceVersion(nvf[0])
                toAdvise.append(((nvf[0], version, nvf[2]), srpm))


        log.info('found %s troves to update, and %s troves to send advisories'
                 % (len(toUpdate), len(toAdvise)))
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

    def _sanitizeTrove(self, nvf, srpm, expectedRemovals=None):
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
        @return needsUpdate boolean
        @raises UpdateGoesBackwardsError
        @raises UpdateRemovesPackageError
        """

        needsUpdate = False
        newNames = [ (x.name, x.arch) for x in self._pkgSource.srcPkgMap[srpm] ]
        metadata = None
        removedPackages = set()
        reusedPackages = set()

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
            line = os.path.normpath(line)
            if line in self._pkgSource.locationMap:
                binPkg = self._pkgSource.locationMap[line]
                srcPkg = self._pkgSource.binPkgMap[binPkg]
            else:
                if metadata is None:
                    pkgs = self._getMetadataFromConaryRepository(nvf[0],
                                                                 version=nvf[1])
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
                log.warn('version goes backwards %s -> %s' %
                         (srcPkg.getNevra(), srpm.getNevra()))
                raise UpdateGoesBackwardsError(why=(srcPkg, srpm))

            # make sure we aren't trying to remove a package
            if ((binPkg.name, binPkg.arch) not in newNames and
                not self._cfg.disableUpdateSanity):
                # Novell releases updates to only the binary rpms of a package
                # that have chnaged. We have to use binaries from the old srpm.
                # Get the last version of the pkg and add it to the srcPkgMap.
                pkgs = list(self._pkgSource.binNameMap[binPkg.name])

                # get the correct arch
                pkg = [ x for x in self._getLatestOfAvailableArches(pkgs)
                        if x.arch == binPkg.arch ][0]

                # Raise an exception if the versions of the packages aren't
                # equal or the discovered package comes from a different source.
                if (rpmvercmp(pkg.epoch, srpm.epoch) != 0 or
                    rpmvercmp(pkg.version, srpm.version) != 0 or
                    # in the suse case we have to ignore release
                    (self._cfg.reuseOldRevisions or
                     rpmvercmp(pkg.release, srpm.release) != 0) or
                    # binary does not come from the same source as it used to
                    self._pkgSource.binPkgMap[pkg].name != srpm.name):
                    log.warn('update removes package (%s) %s -> %s'
                             % (pkg.name, srpm.getNevra(), srcPkg.getNevra()))

                    # allow some packages to be removed.
                    if expectedRemovals and pkg.name in expectedRemovals:
                        log.info('package removal (%s) handled in configuration'
                                 % pkg.name)
                        continue

                    removedPackages.add(pkg)

                if not removedPackages:
                    reusedPackages.add(pkg)
                    #log.warn('using old version of package %s' % (pkg, ))
                    #self._pkgSource.srcPkgMap[srpm].add(pkg)

        if removedPackages:
            pkgList=sorted(removedPackages)
            raise UpdateRemovesPackageError(pkgList=pkgList,
                pkgNames=' '.join([str(x) for x in pkgList]),
                newspkg=srpm, oldspkg=srcPkg,
                oldNevra=str(' '.join(srcPkg.getNevra())),
                newNevra=str(' '.join(srpm.getNevra())))

        if reusedPackages:
            pkgList=sorted(reusedPackages)
            raise UpdateReusesPackageError(pkgList=pkgList,
                pkgNames=' '.join([str(x) for x in pkgList]),
                newspkg=srpm, oldspkg=srcPkg,
                oldNevra=str(' '.join(srcPkg.getNevra())),
                newNevra=str(' '.join(srpm.getNevra())))

        return needsUpdate

    def sanityCheckSource(self, srpm):
        """
        Look up the matching source version in the conary repository and verify
        that the manifest matches the package list in the package source.
        @param srpm: src pacakge object
        @type srpm: repomd.packagexml._Package
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

        assert len(nvflst) == 1
        n, v, f = nvflst[0]
        nvf = (n.split(':')[0], v, None)

        needsUpdate = self._sanitizeTrove(nvf, srpm)

        # If anything has chnaged raise an error.
        if needsUpdate:
            raise RepositoryPackageSourceInconsistencyError(nvf=nvf, srpm=srpm)

    @staticmethod
    def _getLatestOfAvailableArches(pkgLst):
        """
        Given a list of package objects, find the latest versions of each
        package for each name/arch.
        @param pkgLst: list of packages
        @type pkgLst: [repomd.packagexml._Package, ...]
        """

        pkgLst.sort()

        pkgMap = {}
        for pkg in pkgLst:
            key = pkg.name + pkg.arch
            if key not in pkgMap:
                pkgMap[key] = pkg
                continue

            # check if newer, first wins
            if util.packagevercmp(pkg, pkgMap[key]) in (1, ):
                pkgMap[key] = pkg

        ret = pkgMap.values()
        ret.sort()

        return ret

    def create(self, pkgNames=None, buildAll=False, recreate=False, toCreate=None):
        """
        Import a new package into the repository.
        @param pkgNames: list of packages to import
        @type pkgNames: list
        @param buildAll: return a list of all troves found rather than just the new ones.
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
        for pkg in sorted(toCreate):
            try:
                # Only import packages that haven't been imported before
                version = verCache.get('%s:source' % pkg.name)
                if not version or recreate:
                    log.info('attempting to import %s' % pkg)
                    version = self.update((pkg.name, None, None), pkg)

                if not verCache.get(pkg.name) or buildAll or recreate:
                    if self.isPlatformTrove(version):
                        toBuild.add((pkg.name, version, None))
                    else:
                        parentPackages.add((pkg.name, version, None))
                else:
                    log.info('not building %s' % pkg.name)
                    preBuiltPackages.add((pkg.name, version, None))
            except Exception, e:
                raise
                log.error('failed to import %s: %s' % (pkg, e))
                fail.add((pkg, e))

        if buildAll and pkgs and pkgNames:
            toBuild.update(
                [ (x, self._conaryhelper.getLatestSourceVersion(x), None)
                  for x in pkgs if not self._fltrPkg(x) ]
            )

        # Find all of the binaries that match the upstream platform sources.
        log.info('looking up binary versions of all parent platform packages')
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
        # pylint: disable-msg=W0612

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

        manifest = self._getManifestFromPkgSource(srcPkg)
        self._conaryhelper.setManifest(nvf[0], manifest)

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
        baseManifest = sorted([ os.path.basename(x) for x in manifest ])
        parentBaseManifest = sorted([ os.path.basename(x)
                                      for x in parentManifest ])

        if baseManifest != parentBaseManifest:
            log.error('found matching parent trove, but manifests differ')
            raise ParentPlatformManifestInconsistencyError(srcPkg=srcPkg,
                manifest=manifest, parentManifest=parentManifest)

        return srcVersion

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
                if hasattr(pkg, 'location'):
                    manifest.append(pkg.location)
                elif hasattr(pkg, 'files'):
                    manifest.extend(pkg.files)
        return manifest

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
                        log.warn('found virtual requires %s in pkg %s' % (name, srcPkg.name))
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

    def publish(self, trvLst, expected, targetLabel, checkPackageList=True):
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
        """

        return self._conaryhelper.promote(
            trvLst,
            expected,
            self._cfg.sourceLabel,
            targetLabel,
            checkPackageList=checkPackageList,
            extraPromoteTroves=self._cfg.extraPromoteTroves
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

        # FIXME: figure out why conary does't let you set metadata on
        #        source troves.
        #trvSpecs.append(srcTrvSpec)

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
