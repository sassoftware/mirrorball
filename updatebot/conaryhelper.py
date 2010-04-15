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
Module to wrap around conary api. Maybe this could be replaced by rbuild at
some point.
"""

import os
import time
import logging
import tempfile
import itertools

import conary
from conary import trove
from conary import state
from conary import checkin
from conary.deps import deps
from conary.build import use
from conary import conarycfg
from conary import conaryclient
from conary.lib import log as clog
from conary.conaryclient import mirror
from conary import errors as conaryerrors

from updatebot.lib import util
from updatebot.lib import xobjects
from updatebot.errors import GroupNotFound
from updatebot.errors import TooManyFlavorsFoundError
from updatebot.errors import NoManifestFoundError
from updatebot.errors import NoCheckoutFoundError
from updatebot.errors import PromoteFailedError
from updatebot.errors import PromoteMismatchError
from updatebot.errors import MirrorFailedError
from updatebot.errors import BinariesNotFoundForSourceVersion

from updatebot.lib.conarycallbacks import UpdateBotCloneCallback

log = logging.getLogger('updatebot.conaryhelper')

class ConaryHelperSharedCache(object):
    def __init__(self):
        self.clear()

    def clear(self):
        # caches source names and versions for binaries past into
        # getSourceVersions.
        # binTroveSpec: sourceTroveSpec
        self.sourceVersionCache = {}

        # Keep a cache of all binary versions that have been looked up in
        # getBinaryVersions to avoid lots of expensive getTroveVersionsByLabel
        # calls.
        # frzenset(labels): binTroveNVFSet
        self.binaryVersionCache = {}

        # Cache cloned from information
        # srcNVF: destNVF
        self.clonedFromCache = {}
        self.labelClonedFromCache = {}

        self.conaryConfigCache = {}
        self.sharedTmpDir = None


class ConaryHelper(object):
    """
    Wrapper object for conary api.
    """

    _cache = ConaryHelperSharedCache()

    def __init__(self, cfg):
        self._groupFlavorCount = len(cfg.groupFlavors)

        if not self._cache.sharedTmpDir:
            self._cache.sharedTmpDir = tempfile.mkdtemp(
                prefix='conaryhelper-tmpdir-')

        conaryCfgFile = util.join(cfg.configPath, 'conaryrc')
        if conaryCfgFile in self._cache.conaryConfigCache:
            self._ccfg = self._cache.conaryConfigCache[conaryCfgFile]
        else:
            self._ccfg = conarycfg.ConaryConfiguration(readConfigFiles=False)
            self._ccfg.read(conaryCfgFile)
            self._ccfg.dbPath = ':memory:'
            # Have to initialize flavors to commit to the repository.
            self._ccfg.initializeFlavors()

            # FIXME: CNY-3256 - use unique tmp directory for lookaside until
            #                   this issue is fixed.
            self._ccfg.lookaside = tempfile.mkdtemp(
                dir=self._cache.sharedTmpDir,
                prefix='%s-lookaside-' % cfg.platformName)
            log.info('using lookaside %s' % self._ccfg.lookaside)

            mirrorDir = util.join(cfg.configPath, 'mirrors')
            if os.path.exists(mirrorDir):
                self._ccfg.mirrorDirs.insert(0, mirrorDir)

            self._cache.conaryConfigCache[conaryCfgFile] = self._ccfg

        self._mcfg = None
        mcfgfn = util.join(cfg.configPath, 'mirror.conf')
        if mcfgfn in self._cache.conaryConfigCache:
            self._mcfg = self._cache.conaryConfigCache[mcfgfn]
        elif os.path.exists(mcfgfn):
            self._mcfg = mirror.MirrorFileConfiguration()
            self._mcfg.read(mcfgfn)
            self._cache.conaryConfigCache[mcfgfn] = self._mcfg

        self._client = conaryclient.ConaryClient(self._ccfg)
        self._repos = self._client.getRepos()

        self._newPkgFactory = cfg.newPackageFactory

        self._checkoutCache = {}
        self._cacheDir = tempfile.mkdtemp(
            dir=self._cache.sharedTmpDir,
            prefix='conaryhelper-%s-' % cfg.platformName)

    def clearCache(self):
        """
        Clear the trove query cache.
        """

        self._cache.clear()

    def getConaryConfig(self):
        """
        Get a conary config instance.
        @return conary configuration object
        """

        return self._ccfg

    def findTrove(self, nvf, *args, **kwargs):
        """
        Mapped to conaryclient.repos.findTrove. Will always search buildLabel.
        """

        trvs = self.findTroves([ nvf, ], *args, **kwargs)
        assert len(trvs) in (0, 1)

        if trvs:
            return trvs.values()[0]
        else:
            return []

    def findTroves(self, troveList, labels=None, *args, **kwargs):
        """
        Mapped to conaryclient.repos.findTroves. Will always search buildLabel.
        """

        if not labels:
            labels = self._ccfg.buildLabel

        try:
            return self._repos.findTroves(labels, troveList, *args, **kwargs)
        except conaryerrors.TroveNotFound, e:
            return {}

    def isOnBuildLabel(self, version):
        """
        Check if version is on the build label.
        @param version: conary version object
        @type version: conary.versions.Version
        @return True if version is on the buildLabel.
        @rtype boolean
        """

        if hasattr(version, 'label'):
            label = version.label()
        else:
            label = version.trailingLabel()

        return self._ccfg.buildLabel == label

    def getSourceTroves(self, group):
        """
        Find all of the source troves included in group. If group is None use
        the top level group config option.
        @param group: group to query
        @type group: None or troveTuple (name, versionStr, flavorStr)
        @return dict of source trove specs to list of binary trove specs
        """

        # E1101 - Instance of 'ConaryConfiguration' has no 'buildLabel' member
        # pylint: disable-msg=E1101

        try:
            trvlst = self._repos.findTrove(self._ccfg.buildLabel, group)
        except conary.errors.TroveNotFound:
            raise GroupNotFound(group=group, label=self._ccfg.buildLabel)

        latest = self._findLatest(trvlst)

        if len(latest) != self._groupFlavorCount:
            raise TooManyFlavorsFoundError(why=latest)

        d = {}
        for trv in latest:
            log.info('querying %s for source troves' % (trv, ))
            srcTrvs = self._getSourceTroves(trv)
            for src, binLst in srcTrvs.iteritems():
                s = set(binLst)
                if src in d:
                    d[src].update(s)
                else:
                    d[src] = s

        return d

    @staticmethod
    def _findLatest(trvlst):
        """
        Given a list of trove specs, find the most recent versions.
        @param trvlst: list of trove specs
        @type trvlst: [(name, versionObj, flavorObj), ...]
        @return [(name, versionObj, flavorObj), ...]
        """

        latest = []

        trvlst.sort()
        trvlst.reverse()
        while len(trvlst) > 0:
            trv = trvlst.pop(0)
            if len(latest) == 0 or latest[-1][1] == trv[1]:
                latest.append(trv)
            else:
                break

        return latest

    def _iterPathsByTrove(self, troveSpecList):
        """
        Generates (name, set of paths) tuples representing the paths
        contained in troves mentioned in the troveSpecList
        @param troveSpecList: troves to inspect
        @type troveSpecList: [(name, versionObj, flavorObj), ...]
        @yield (name, frozenset(path, path, ...))
        """
        cl = [ (x, (None, None), (y, z), True) for x, y, z in troveSpecList ]
        cs = self._client.createChangeSet(cl, withFiles=True,
                                          withFileContents=False,
                                          recurse=False)
        for trvCs in cs.iterNewTroveList():
            trv = trove.Trove(trvCs)
            paths = frozenset(path for _, path, _, _ in trv.iterFileList())
            if paths:
                yield trv.name(), paths

    def _getSourceTroves(self, troveSpec):
        """
        Iterate over the contents of a trv to find all of source troves
        refrenced by that trove.
        @param troveSpec: trove to walk.
        @type troveSpec: (name, versionObj, flavorObj)
        @return {srcTrvSpec: [binTrvSpec, binTrvSpec, ...]}
        """

        # W0212 - Access to a protected member _TROVEINFO_TAG_SOURCENAME of a
        #         client class
        # pylint: disable-msg=W0212

        name, version, flavor = troveSpec
        cl = [ (name, (None, None), (version, flavor), True) ]
        cs = self._client.createChangeSet(cl, withFiles=False,
                                          withFileContents=False,
                                          recurse=False)

        # Iterate over both strong and weak refs because msw said it was a
        # good idea.
        topTrove = self._getTrove(cs, name, version, flavor)
        troves = topTrove.iterTroveList(weakRefs=True, strongRefs=True)

        return self.getSourceVersions(list(troves))

    def _cacheTroveInfo(self, troveSpecs, cache, tiType, tiFunc=None):
        """
        Retrieve a bit of trove info for a listed trove specs and cache the
        results.
        @param troveSpecs: list of destination nvfs
        @type troveSpecs: iterable of (name, verObj, flvObj) tuples.
        @param cache: cache of trove spec to trove info
        @type cache: dict(trvSpec=trvInfo)
        @param tiType: trove info field to cache on
        @type tiType: conary.trove._TROVEINFO_TAG_*
        @param tiFunc: optional function to format trove info into the desired
                       value. This will be passed two arguments, the trove info
                       and the trvSpec this applies to.
        @type tiFunc: function
        """

        # filter out already cached results
        cached = set(x for x in troveSpecs if x in cache)
        uncached = sorted(set(troveSpecs).difference(cached))

        req = []
        for n, v, f in uncached:
            if n.endswith(':source'):
                f = deps.parseFlavor('')
            req.append((n, v, f))

        tiMap = {}
        tiLst = self._repos.getTroveInfo(tiType, req)
        for i, nvf in enumerate(uncached):
            ti = tiLst[i]()
            if tiFunc:
                ti = tiFunc(ti, nvf)
            tiMap.setdefault(ti, set()).add(nvf)
            cache[nvf] = ti

        for spec in cached:
            tiMap.setdefault(cache[spec], set()).add(spec)

        return tiMap

    def getClonedFrom(self, troveSpecs):
        """
        Get a mapping of cloned from trove info for a list of trove specs in the
        form srcSpec: destSpec.
        @param troveSpecs: list of destination nvfs
        @type troveSpecs: iterable of (name, verObj, flvObj) tuples.
        """

        def tiFunc(ti, nvf):
            return (nvf[0], ti, nvf[2])

        return self._cacheTroveInfo(troveSpecs, self._cache.clonedFromCache,
            trove._TROVEINFO_TAG_CLONEDFROM, tiFunc=tiFunc)

    def getClonedFromForLabel(self, label):
        """
        Get a mapping of cloned from trove info for all versions on a label.
        @param label: conary label
        @type label: conary.versions.Label
        """

        if hasattr(label, 'label'):
            label = label.label()

        if label in self._cache.labelClonedFromCache:
            return self._cache.labelClonedFromCache[label]

        req = {None: {label: None}}
        binTrvMap = self._repos.getTroveVersionsByLabel(req)

        binTrvs = set()
        for n, vMap in binTrvMap.iteritems():
            for v, flvs in vMap.iteritems():
                if n.endswith(':source'):
                    binTrvs.add((n, v, None))
                else:
                    binTrvs.update(set((n, v, x) for x in flvs))

        cfMap = self.getClonedFrom(binTrvs)

        ret = {}
        for f, t in cfMap.iteritems():
            assert len(cfMap[f]) == 1
            ret[f] = list(t)[0]

        self._cache.labelClonedFromCache[label] = ret
        return ret

    def getSourceVersions(self, binTroveSpecs):
        """
        Given a list of trove specs, query the repository for all of the related
        source versions.
        @param binTroveSpecs: list of troves to query for.
        @type binTroveSpecs: [(name, versionObj, flavObj), ... ]
        @return {srcTrvSpec: [binTrvSpec, binTrvSpec, ...]}
        """

        def tiFunc(ti, nvf):
            return (ti, nvf[1].getSourceVersion(), None)

        return self._cacheTroveInfo(binTroveSpecs, self._cache.sourceVersionCache,
            trove._TROVEINFO_TAG_SOURCENAME, tiFunc=tiFunc)

    def getBinaryVersions(self, srcTroveSpecs, labels=None, latest=True,
        includeBuildLabel=False, missingOk=False):
        """
        Given a list of source trove specs, find the latest versions of all
        binaries generated from these sources.
        @param srcTroveSpecs: list of source troves.
        @type srcTroveSpecs: [(name, versionObj, None), ... ]
        @param labels: list of labels to search, defaults to the buildLabel
        @type labels: list(conary.versions.Label, ...)
        @param latest: get only the latest binaries.
        @type latest: boolean
        @param includeBuildLabel: search the build label in addition to
                                  specified labels.
        @type includeBuildLabel: boolean
        @param missingOk: If False, raise an error when binaries can not be
                          found for a given source trove.
        @type missingOk: boolean
        @return {srcTrvSpec: [binTrvSpec, binTrvSpec, ... ]}
        """

        # default to the build label if not other labels were specified
        if not labels:
            labels = [ self._ccfg.buildLabel, ]

        # Insert build label if it isn't already in the list
        if includeBuildLabel and self._ccfg.buildLabel not in labels:
            labels.insert(0, self._ccfg.buildLabel)

        # Needs to be a frozenset so that it is hashable.
        labels = frozenset(labels)

        # FIXME: If this is ever used in a long running process the cache will
        #        need to be refreshed and/or expired.

        # Check the cache before going on.
        if labels in self._cache.binaryVersionCache:
            binTrvSpecs = self._cache.binaryVersionCache[labels]
        else:
            # get all binary trove specs for the specified labels
            req = {None: dict([ (x, None) for x in labels ])}
            binTrvMap = self._repos.getTroveVersionsByLabel(req)

            # build a list of the binary troves on the labels
            binTrvSpecs = set()
            for n, vermap in binTrvMap.iteritems():
                # filter out sources
                if n.endswith(':source'):
                    continue
                for v, flvs in vermap.iteritems():
                    for f in flvs:
                        binTrvSpecs.add((n, v, f))

            # Populate cache.
            self._cache.binaryVersionCache[labels] = binTrvSpecs

        # get a map of source trove specs to binary trove specs
        srcVerMap = self.getSourceVersions(binTrvSpecs)

        srcMap = {}
        for srcTrv in srcTroveSpecs:
            if srcTrv not in srcVerMap:
                msg = ('can not find binaries for requested source trove in '
                       'repository %s' % (srcTrv, ))
                if missingOk:
                    log.warn(msg)
                    continue
                log.error(msg)
                raise BinariesNotFoundForSourceVersion(srcName=srcTrv[0],
                                                       srcVersion=srcTrv[1])

            # Move binaries into a more convienient data structure.
            binTrvMap = {}
            binTrvs = srcVerMap[srcTrv]
            for binTrv in binTrvs:
                binTrvMap.setdefault(binTrv[1], set()).add(binTrv)

            if latest:
                # find the latest version.
                latestVer = None
                for binVer in binTrvMap:
                    if latestVer is None:
                        latestVer = binVer
                        continue
                    if latestVer < binVer:
                        latestVer = binVer

                # Store latest binary versions in source version map
                assert srcTrv not in srcMap
                srcMap[srcTrv] = binTrvMap[latestVer]
            else:
                srcMap[srcTrv] = [ x for x in
                                   itertools.chain(*binTrvMap.values()) ]

        return srcMap

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
        @param includeBuildLabel: search the build label in addition to
                                  specified labels.
        @return {srcTrvSpec: [binTrvSpec, binTrvSpec, ...]}
        """

        trvs = self.findTrove((n, v, f), labels=labels)
        srcVersions = self.getSourceVersions(trvs)
        srcSpecs = srcVersions.keys()
        srcMap = self.getBinaryVersions(srcSpecs, labels=labels, latest=latest,
            includeBuildLabel=includeBuildLabel)
        return srcMap

    @staticmethod
    def _getTrove(cs, name, version, flavor):
        """
        Get a trove object for a given name, version, flavor from a changeset.
        @param cs: conary changeset object
        @type cs: changeset
        @param name: name of a trove
        @type name: string
        @param version: conary version object
        @type version: conary.versions.Version
        @param flavor: conary flavor object
        @type flavor: conary.deps.Flavor
        @return conary.trove.Trove object
        """

        #log.debug('getting trove for (%s, %s, %s)' % (name, version, flavor))
        troveCs = cs.getNewTroveVersion(name, version, flavor)
        trv = trove.Trove(troveCs, skipIntegrityChecks=True)
        return trv

    def getManifest(self, pkgname, version=None):
        """
        Get the contents of the manifest file from the source component for a
        given package.
        @param pkgname: name of the package to retrieve
        @type pkgname: string
        @param version optional source version to checkout.
        @type version conary.versions.Version
        @return manifest for pkgname
        """

        log.info('retrieving manifest for %s' % pkgname)
        recipeDir = self._edit(pkgname, version=version)
        manifestFileName = util.join(recipeDir, 'manifest')

        if not os.path.exists(manifestFileName):
            raise NoManifestFoundError(pkgname=pkgname, dir=recipeDir)

        manifest = [ x.strip() for x in open(manifestFileName) ]
        return manifest

    def setManifest(self, pkgname, manifest):
        """
        Create/Update a manifest file.
        @param pkgname: name of the package
        @type pkgname: string
        @param manifest: list of files to go in the manifest file
        @type manifest: list(string, string, ...)
        """

        log.info('setting manifest for %s' % pkgname)

        recipeDir = self._edit(pkgname)

        # Update manifest file.
        manifestFileName = util.join(recipeDir, 'manifest')
        manifestfh = open(manifestFileName, 'w')
        manifestfh.write('\n'.join(manifest))
        manifestfh.write('\n')
        manifestfh.close()

        # Make sure manifest file has been added.
        self._addFile(recipeDir, 'manifest')

    def getMetadata(self, pkgname, version=None):
        """
        Get the metadata.xml file from a source componet named pkgname.
        @param pkgname name of the package to checkout
        @type pkgname string
        @return list like object
        @param version optional source version to checkout.
        @type version conary.versions.Version
        """

        log.info('retrieving metadata for %s' % pkgname)
        recipeDir = self._edit(pkgname, version=version)
        metadataFileName = util.join(recipeDir, 'metadata.xml')

        if not os.path.exists(metadataFileName):
            return set()

        xml = open(metadataFileName).read()
        xMetadata = xobjects.XMetadataDoc.thaw(xml)

        pkgs = set(xMetadata.data.binaryPackages)
        pkgs.add(xMetadata.data.sourcePackage)

        return pkgs

    def setMetadata(self, pkgname, metadata):
        """
        Create/Update metadata.xml in a source component.
        @param pkgname name of the package
        @type pkgname string
        @param list of pkg objects
        @type metadata string
        """

        log.info('setting metadata for %s' % pkgname)

        recipeDir = self._edit(pkgname)

        xMetadata = xobjects.XMetadataDoc(data=metadata)
        xml = xMetadata.freeze()

        # Update metadata file.
        metadataFileName = util.join(recipeDir, 'metadata.xml')
        metadatafh = open(metadataFileName, 'w')
        metadatafh.write(xml)
        metadatafh.write('\n')
        metadatafh.close()

        # Make sure metadata file has been added.
        self._addFile(recipeDir, 'metadata.xml')

    def getBuildRequires(self, pkgname):
        """
        Get the build requires defined in the buildrequires file.
        @param pkgname: name of the package to retrieve
        @type pkgname: string
        @return list of build requires
        """

        log.info('retrieving buildrequires for %s' % pkgname)
        recipeDir = self._edit(pkgname)
        buildRequiresFileName = util.join(recipeDir, 'buildrequires')

        if not os.path.exists(buildRequiresFileName):
            return []

        buildRequires = [ x.strip() for x in open(buildRequiresFileName) ]
        return buildRequires

    def setBuildRequires(self, pkgname, buildrequires):
        """
        Set the contents of the build requires file in the repository.
        @param pkgname: name of hte package to edit
        @type pkgname: string
        @param buildrequires: list of build requires, source names tuples
        @type buildrequires: list of two tuples
        """

        log.info('setting buildrequires for %s' % pkgname)

        recipeDir = self._edit(pkgname)
        buildRequiresFileName = util.join(recipeDir, 'buildrequires')

        # generate buildrequires file
        buildRequiresfh = open(buildRequiresFileName, 'w')
        for buildreq in buildrequires:
            buildRequiresfh.write(' '.join(buildreq))
            buildRequiresfh.write('\n')
        buildRequiresfh.close()

        # add file to the source compoent
        self._addFile(recipeDir, 'buildrequires')

    def getVersion(self, pkgname, version=None):
        """
        Get the version of the specified package if this package has a version
        file in the source component, otherwise return None.
        @param pkgname: name of hte package to edit
        @type pkgname: string
        @param version optional source version to checkout.
        @type version conary.versions.Version
        """

        log.info('getting version info for %s' % pkgname)

        recipeDir = self._edit(pkgname, version=version)
        versionFileName = util.join(recipeDir, 'version')

        if not os.path.exists(versionFileName):
            return None

        version = open(versionFileName).read().strip()
        return version

    def setVersion(self, pkgname, version):
        """
        Set the version of the specified package, for this to be meaningful
        there must be a factory that consumes this data.
        @param pkgname: name of hte package to edit
        @type pkgname: string
        @param version: upstream version of the package, required to be a valid
                        conary version.
        @type version: string
        """

        log.info('setting version info for %s' % pkgname)

        recipeDir = self._edit(pkgname)
        versionFileName = util.join(recipeDir, 'version')

        # write version info
        versionfh = open(versionFileName, 'w')
        versionfh.write(version)

        # source files must end in a trailing newline
        versionfh.write('\n')

        versionfh.close()

        # make sure version file has been added to package
        self._addFile(recipeDir, 'version')

    def commit(self, pkgname, version=None, commitMessage=''):
        """
        Commit the cached checkout of a source component.
        @param pkgname name of the package
        @type pkgname string
        @param commitMessage: optional argument for setting the commit message
                              to use when committing to the repository.
        @type commitMessage: string
        @param version optional source version to checkout.
        @type version conary.versions.Version
        @return version of the source commit.
        """

        pkgkey = (pkgname, version)
        if pkgkey not in self._checkoutCache:
            raise NoCheckoutFoundError(pkgname=pkgname)

        # Setup flavor objects
        use.setBuildFlagsFromFlavor(pkgname, self._ccfg.buildFlavor,
                                    error=False)

        # Commit to repository.
        recipeDir = self._checkoutCache[pkgkey]
        self._commit(recipeDir, commitMessage)

        # Get new version of the source trove.
        version = self.getLatestSourceVersion(pkgname)
        assert version is not None
        return version

    def _edit(self, pkgname, version=None):
        """
        Checkout/Create source checkout.
        @param pkgname name of the package
        @type pkgname string
        @param version optional source version to checkout.
        @type version conary.versions.Version
        @return path to checkout
        """

        pkgkey = (pkgname, version)
        if pkgkey in self._checkoutCache:
            return self._checkoutCache[pkgkey]

        # Figure out if we should create or update.
        if (not self.getLatestSourceVersion(pkgname) and
            (version is None or self.isOnBuildLabel(version))):
            assert version is None
            recipeDir = self._newpkg(pkgname)
        else:
            recipeDir = self._checkout(pkgname, version=version)

        self._checkoutCache[pkgkey] = recipeDir
        self._checkoutCache[recipeDir] = pkgkey

        return recipeDir

    def _getRecipeDir(self, pkgname):
        """
        Make a temporary directory to create or checkout a package in.
        @param pkgname: name of the package to checkout
        @type pkgname: string
        @return checkout directory
        """

        return tempfile.mkdtemp(prefix='%s-' % pkgname, dir=self._cacheDir)

    def _checkout(self, pkgname, version=None):
        """
        Checkout a source component from the repository.
        @param pkgname: name of the package to checkout
        @type pkgname: string
        @param version optional source version to checkout.
        @type version conary.versions.Version
        @return checkout directory
        """

        troveSpec = pkgname
        if version:
            troveSpec += '=%s' % version

        log.info('checking out %s' % troveSpec)

        req = (pkgname, version, None)
        coMap = self._multiCheckout([ req, ])
        recipeDir = coMap[req]

        return recipeDir

    def _newpkg(self, pkgname):
        """
        Create a new source component.
        @param pkgname: name of the package to create.
        @type pkgname: string
        @return checkout directory
        """

        log.info('creating new package %s' % pkgname)

        recipeDir = self._getRecipeDir(pkgname)
        cwd = os.getcwd()
        try:
            os.chdir(recipeDir)
            checkin.newTrove(self._repos, self._ccfg, pkgname,
                             factory=self._newPkgFactory)
        finally:
            os.chdir(cwd)

        return util.join(recipeDir, pkgname)

    def _commit(self, pkgDir, commitMessage):
        """
        Commit a source trove to the repository.
        @param pkgDir: directory returned by checkout
        @type pkgDir: string
        @param commitMessage: commit message to use.
        @type commitMessage: string
        """

        log.info('committing %s' % os.path.basename(pkgDir))

        cwd = os.getcwd()
        try:
            os.chdir(pkgDir)
            checkin.commit(self._repos, self._ccfg, commitMessage)
            if pkgDir in self._checkoutCache:
                pkgName = self._checkoutCache[pkgDir]
                del self._checkoutCache[pkgName]
                del self._checkoutCache[pkgDir]
        finally:
            os.chdir(cwd)
            util.rmtree(pkgDir)

    @staticmethod
    def _addFile(pkgDir, fileName):
        """
        Add a file to a source component.
        @param pkgDir: directory where package is checked out to.
        @type pkgDir: string
        @param fileName: file name to add.
        @type fileName: string
        """

        log.info('adding file: %s' % fileName)

        cwd = os.getcwd()
        try:
            os.chdir(pkgDir)
            checkin.addFiles([fileName, ], ignoreExisting=True, text=True)
        finally:
            os.chdir(cwd)

    @staticmethod
    def _removeFile(pkgDir, fileName):
        """
        Remove a file from a source component.
        @param pkgDir: directory where package is checked out to.
        @type pkgDir: string
        @param fileName: file name to add.
        @type fileName: string
        """

        log.info('removing file: %s' % fileName)

        cwd = os.getcwd()
        try:
            os.chdir(pkgDir)
            checkin.removeFile(fileName)
        finally:
            os.chdir(cwd)

    def _getVersionsByName(self, pkgname):
        """
        Figure out if a trove exists in the repository.
        @param pkgname: name of the package to look for.
        @type pkgname: string
        """

        # E1101 - Instance of 'ConaryConfiguration' has no 'buildLabel' member
        # pylint: disable-msg=E1101

        label = self._ccfg.buildLabel

        trvMap = self._repos.getTroveLeavesByLabel({pkgname: {label: None }})
        verMap = trvMap.get(pkgname, {})
        versions = verMap.keys()
        return versions

    def getLatestSourceVersion(self, pkgname):
        """
        Finds the latest version of pkgname:source.
        @param pkgname: name of package to look for
        @type pkgname: string
        """

        versions = self._getVersionsByName('%s:source' % pkgname)

        # FIXME: This is a hack to work around the fact that ubuntu has some
        #        shadows and packages that overlap on the label,
        #        _getVersionsByName needs to be smarter.
        if len(versions) > 1:
            versions = [ x for x in versions if not x.isShadow() ]

        assert len(versions) in (0, 1)

        if len(versions) == 1:
            return versions[0]

        return None

    def _getLatestTroves(self):
        """
        Get a dict of the latest troves on the buildLabel.
        @return {name: {version: [flavor, ...]}}}
        """

        label = self._ccfg.buildLabel

        # Filter by buildFlavor to handle mutli stage bootstrap cases where you
        # want to build all packages that haven't yet been built !bootstrap.
        flavors = set()
        for section in self._ccfg._sections.itervalues():
            if hasattr(section, 'buildFlavor'):
                flavors.add(section.buildFlavor)

        trvMap = self._repos.getTroveLeavesByLabel({None: {label: flavors}})

        # Remove anything with multiple versions, this results from something
        # changing flavor at any point.
        for name, verDict in trvMap.iteritems():
            if len(verDict) == 1:
                continue
            versions = verDict.keys()
            versions.sort()
            latest = versions[-1]
            versions.remove(latest)
            for version in versions:
                for flavor in verDict[version]:
                    log.warn('removing extra version of %s=%s[%s]' % 
                             (name, version, flavor))
                del trvMap[name][version]

        return trvMap

    def getLatestVersions(self):
        """
        Find all of the versions on the buildLabel.
        @return {trvName: trvVersion}
        """

        trvMap = self._getLatestTroves()

        verMap = {}
        for name, verDict in trvMap.iteritems():
            if len(verDict) > 1:
                vers = verDict.keys()
                vers.sort()
                ver = vers[-1]
            else:
                ver = verDict.keys()[0]
            verMap[name] = ver

        return verMap

    def promote(self, trvLst, expected, sourceLabels, targetLabel,
                checkPackageList=True, extraPromoteTroves=None,
                extraExpectedPromoteTroves=None, commit=True):
        """
        Promote a group and its contents to a target label.
        @param trvLst: list of troves to publish
        @type trvLst: [(name, version, flavor), ... ]
        @param expected: list of troves that are expected to be published.
        @type expected: [(name, version, flavor), ...]
        @param sourceLabels: list of labels that should be flattened onto the
                             targetLabel.
        @type sourceLabels: [labelObject, ... ]
        @param targetLabel: table to publish to
        @type targetLabel: conary Label object
        @param checkPackageList: verify the list of packages being promoted or
                                 not.
        @type checkPackageList: boolean
        @param extraPromoteTroves: troves to promote in addition to the troves
                                   that have been built.
        @type extraPromoteTroves: list of trove specs.
        @param extraExpectedPromoteTroves: list of trove nvfs that are expected
                                           to be promoted, but are only filtered
                                           by name, rather than version and
                                           flavor.
        @type extraExpectedPromoteTroves: list of name, version, flavor tuples
                                          where version and flavor may be None.
        @param commit: commit the promote changeset or just return it.
        @type commit: boolean
        """

        start = time.time()
        log.info('starting promote')
        log.info('creating changeset')

        # make extraPromoteTroves a set if it was not specified.
        if extraPromoteTroves is None:
            extraPromoteTroves = set()
        else:
            extraPromoteTroves = set(extraPromoteTroves)

        # make extraExpectedPromoteTroves a list if it is not specified.
        if extraExpectedPromoteTroves is None:
            extraExpectedPromoteTroves = set()
        else:
            extraExpectedPromoteTroves = set(extraExpectedPromoteTroves)

        # make sure trvLst is a list.
        trvLst = list(trvLst)

        # Get the label that the group is on.
        fromLabel = trvLst[0][1].trailingLabel()

        # Build the label map.
        labelMap = {fromLabel: targetLabel}
        for label in sourceLabels:
            assert label is not None
            labelMap[label] = targetLabel

        # mix in the extra troves
        for n, v, f in extraPromoteTroves:
            trvs = self._repos.findTrove(fromLabel, (n, v, f))
            latestVer = trvs[0][1]
            for name, version, flavor in trvs:
                if version > latestVer:
                    latestVer = version
            for name, version, flavor in trvs:
                if version == latestVer:
                    trvLst.append((name, version, flavor))

        callback = UpdateBotCloneCallback(self._ccfg, 'automated promote',
            log=log)

        success, cs = self._client.createSiblingCloneChangeSet(
                            labelMap,
                            trvLst,
                            cloneSources=True,
                            callback=callback)

        log.info('changeset created in %s' % (time.time() - start, ))

        if not success:
            raise PromoteFailedError(what=trvLst)

        packageList = [ x.getNewNameVersionFlavor()
                        for x in cs.iterNewTroveList() ]

        oldPkgs = set([ (x[0], x[2]) for x in expected
                        if not x[0].endswith(':source') ])
        newPkgs = set([ (x[0], x[2]) for x in packageList
                        if not x[0].endswith(':source') ])

        # Make sure that all packages being promoted are in the set of packages
        # that we think should be available to promote. Note that all packages
        # in expected will not be promoted because not all packages are
        # included in the groups.
        trvDiff = newPkgs.difference(oldPkgs)
        grpTrvs = set([ (x[0], x[2]) for x in trvLst
                        if not x[0].endswith(':source') ])
        grpDiff = set([ x[0] for x in trvDiff.difference(grpTrvs) ])
        extraTroves = set([ x[0] for x in extraPromoteTroves |
                                          extraExpectedPromoteTroves ])
        if checkPackageList and grpDiff.difference(extraTroves):
            raise PromoteMismatchError(expected=oldPkgs, actual=newPkgs)

        if not commit:
            return cs, packageList

        log.info('committing changeset')

        self._repos.commitChangeSet(cs, callback=callback)

        log.info('changeset committed')
        log.info('promote complete, elapsed time %s' % (time.time() - start, ))

        return packageList

    def mirror(self, fullTroveSync=False):
        """
        Mirror the current platform to the external repository if a
        mirror.conf exists.
        """

        if self._mcfg is None:
            log.info('mirroring disabled, no mirror.conf found for this '
                     'platform')
            return

        log.info('starting mirror')

        # Always use DEBUG logging when mirroring
        curLevel = clog.fmtLogger.level
        clog.setVerbosity(clog.DEBUG)

        callback = mirror.ChangesetCallback()
        rc = mirror.mainWorkflow(cfg=self._mcfg, callback=callback, sync=fullTroveSync)

        if rc is not None and rc != 0:
            raise MirrorFailedError(rc=rc)

        # Reset loglevel
        clog.setVerbosity(curLevel)

        log.info('mirror complete')

        return rc

    def setTroveMetadata(self, trvSpecs, license=None, desc=None, shortDesc=None):
        """
        Set metadata on a given trove spec.
        """

        if not license and not dec and not shortDesc:
            log.warn('no metadata found for %s' % trvSpecs[-1][0])
            return

        enc = 'utf-8'
        mi = trove.MetadataItem()

        if license:
            mi.licenses.set(license.encode(enc))
        if desc:
            mi.longDesc.set(desc.encode(enc))
        if shortDesc:
            mi.shortDesc.set(shortDesc.encode(enc))

        log.info('setting metadata for %s' % trvSpecs[-1][0].split(':')[0])

        metadata = [ (x, mi) for x in trvSpecs ]
        self._repos.addMetadataItems(metadata)

    def _multiCheckout(self, trvSpecs):
        """
        Checkout several sources at once and return a map of source trove spec
        to checkout directory.
        @param trvSpecs: list of sources to checkout.
        @type trvSpecs: list((name, version, None), ...)
        @return map of source requests to checkout directories
        @rtype dict((name, version, None)=/path/to/checkout)
        """

        # NOTE: This code is strongly based off of conary.checkin._checkout,
        #       which should possibly be refactored to allow something like
        #       this.

        # Make sure everything is :source.
        req = set()
        reqMap = {}
        for n, v, f in trvSpecs:
            nvf = (n, v, f)
            if not n.endswith(':source'):
                n += ':source'
            req.add((n, v, f))
            reqMap[(n, v, f)] = nvf

        # Find all requested versions.
        trvMap = self._repos.findTroves(self._ccfg.buildLabel, req)

        # Build rev map for later lookups.
        revTrvMap = dict([ (y[0], x) for x, y in trvMap.iteritems() ])

        # Get the list of results from the findTroves query.
        trvList = [ x for x in itertools.chain(*trvMap.itervalues()) ]

        # Build a changeset request.
        csJob = [ (x[0], (None, None), (x[1], x[2]), True) for x in trvList ]

        callback = checkin.CheckinCallback(
            trustThreshold=self._ccfg.trustThreshold)

        # Request a changeset with all of the sources except for files that are
        # autosourced.
        cs = self._repos.createChangeSet(csJob,
                                         excludeAutoSource=True,
                                         callback=callback)
        checkin.verifyAbsoluteChangesetSignatures(cs, callback)

        pathMap = {}
        checkoutMap = {}
        sourceStateMap = {}
        conaryStateTargets = {}

        # Prepare to unpack sources from the changeset.
        for nvf in trvList:
            troveCs = cs.getNewTroveVersion(*nvf)
            trv = trove.Trove(troveCs)

            # Create target directory
            targetDir = self._getRecipeDir(nvf[0])
            checkoutMap[reqMap[revTrvMap[nvf]]] = targetDir

            # Store source state
            sourceState = state.SourceState(nvf[0], nvf[1], nvf[1].branch())
            sourceStateMap[trv.getNameVersionFlavor()] = sourceState

            # Store conary state
            conaryState = state.ConaryState(self._ccfg.context, sourceState)
            conaryStateTargets[targetDir] = conaryState

            # Store factory info
            if trv.getFactory():
                sourceState.setFactory(trv.getFactory())

            # Extract file info from changeset
            for (pathId, path, fileId, version) in troveCs.getNewFileList():
                pathMap[(nvf, path)] = (targetDir, pathId, fileId, version)

        # Explode changeset contents.
        checkin.CheckoutExploder(cs, pathMap, sourceStateMap)

        # Write out CONARY state files.
        for targetDir, conaryState in conaryStateTargets.iteritems():
            conaryState.write(targetDir + '/CONARY')

        return checkoutMap

    def cacheSources(self, label, latest=True):
        """
        Checkout all sources on a label and add them to the checkout cache. This
        is significantly more efficient than requesting one sources at a time
        when we know ahead of time that we will fetching all or almost all
        sources.
        @param label: label to search for sources.
        @type label: conary.versions.Label
        @param latest: optional, if True check only latest versions rather
                       than all versions.
        @type latest: boolean
        @return map of source nvf to checkout directories
        @rtype dict((name, version, None)=/path/to/checkout)
        """

        log.info('caching %s sources for %s'
                 % (latest and 'latest' or 'all', label))

        # Find correct query function
        if latest:
            query = self._repos.getTroveLeavesByLabel
        else:
            query = self._repos.getTroveVersionsByLabel

        trvMap = query({None: {label: None}})

        srcSet = set()
        for n, verDict in trvMap.iteritems():
            # skip anything that isn't a source
            if not n.endswith(':source'):
                continue
            for v, flvs in verDict.iteritems():
                srcSet.add((n, v, None))

        coMap = self._multiCheckout(srcSet)

        # Update the checkout cache.
        self._checkoutCache.update(coMap)
        self._checkoutCache.update(dict([ (y, x)
                                          for x, y in coMap.iteritems() ]))

        return coMap
