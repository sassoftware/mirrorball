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
Module for managing conary groups.
"""

import os
import copy
import logging
import itertools

from conary import versions
from conary.deps import deps

from updatebot.lib import util
from updatebot.build import Builder
from updatebot.pkgsource import RpmSource
from updatebot.conaryhelper import ConaryHelper
from updatebot.lib.xobjects import XGroup
from updatebot.lib.xobjects import XGroupDoc
from updatebot.lib.xobjects import XGroupList
from updatebot.lib.xobjects import XPackageDoc
from updatebot.lib.xobjects import XPackageData
from updatebot.lib.xobjects import XPackageItem

from updatebot.errors import OldVersionsFoundError
from updatebot.errors import FlavorCountMismatchError
from updatebot.errors import UnknownBuildContextError
from updatebot.errors import GroupValidationFailedError
from updatebot.errors import UnsupportedTroveFlavorError
from updatebot.errors import UnhandledPackageAdditionError
from updatebot.errors import NameVersionConflictsFoundError
from updatebot.errors import ExpectedRemovalValidationFailedError
from updatebot.errors import UnknownPackageFoundInManagedGroupError

log = logging.getLogger('updatebot.groupmgr')

def checkout(func):
    def wrapper(self, *args, **kwargs):
        if not self._checkedout:
            self._checkout()

        return func(self, *args, **kwargs)
    return wrapper

def commit(func):
    def wrapper(self, *args, **kwargs):
        if self._checkedout:
            self._commit()

        return func(self, *args, **kwargs)
    return wrapper


class GroupManager(object):
    """
    Manage group of all packages for a platform.
    """

    def __init__(self, cfg):
        self._cfg = cfg
        self._helper = GroupHelper(self._cfg)
        self._builder = Builder(self._cfg, rmakeCfgFn='rmakerc-groups')

        #self._versionFactory = VersionFactory(cfg)

        self._sourceName = self._cfg.topSourceGroup[0]
        self._sourceVersion = None

        self._pkgGroupName = 'group-%s-packages' % self._cfg.platformName

        self._checkedout = False
        self._groups = {}

    def _checkout(self):
        """
        Get current group state from the repository.
        """

        self._groups = self._helper.getModel(self._sourceName,
                                             version=self._sourceVersion)
        self._checkedout = True

    def _commit(self, copyToLatest=False):
        """
        Commit current changes to the group.
        """

        if self._sourceVersion and not copyToLatest:
            log.error('refusing to commit out of date source')
            raise NotCommittingOutOfDateSourceError()

        # Copy forward data when we are fixing up old group versions so that
        # this is the latest source.
        if copyToLatest:
            log.info('copying information to latest version')
            # Get data from the old versoin
            version = self._helper.getVersion(self._sourceName, version=self._sourceVersion)
            errataState = self._helper.getErrataState(self._sourceName, version=self._sourceVersion)
            groups = self._groups

            log.info('version: %s' % version)
            log.info('errataState: %s' % errataState)

            # Set version to None to get the latest source.
            self._sourceVersion = None

            # Checkout latest source.
            self._checkout()

            # Set back to old data
            self.setVersion(version)
            self.setErrataState(errataState)
            self._groups = groups

        # sync versions from the package group to the other managed groups.
        self._copyVersions()

        # validate group contents.
        self._validateGroups()

        # write out the model data
        self._helper.setModel(self._sourceName, self._groups)

        # commit to the repository
        version = self._helper.commit(self._sourceName,
                                      version=self._sourceVersion,
                                      commitMessage='automated commit')
        if self._sourceVersion:
            self._sourceVersion = version
        self._checkedout = False
        return version

    save = _commit

    @commit
    def build(self):
        """
        Build all configured flavors of the group.
        """

        groupTroves = ((self._sourceName, self._sourceVersion, None), )
        built = self._builder.cvc.cook(groupTroves)
        return built

    @checkout
    def add(self, *args, **kwargs):
        """
        Add a trove to the package group contents.
        """

        # create package group model if it does not exist.
        if self._pkgGroupName not in self._groups:
            model = GroupContentsModel(self._pkgGroupName)
            self._groups[self._pkgGroupName] = model

        self._groups[self._pkgGroupName].add(*args, **kwargs)

    @checkout
    def remove(self, name):
        """
        Remove a given trove from the package group contents.
        """

        return self._groups[self._pkgGroupName].remove(name)

    def addPackage(self, name, version, flavors):
        """
        Add a package to the model.
        @param name: name of the package
        @type name: str
        @param version: conary version from string object
        @type version: conary.versions.VersionFromString
        @param flavors: list of flavors
        @type flavors: [conary.deps.deps.Flavor, ...]
        """

        # Now that versions are actually used for something make sure they
        # are always present.
        assert version
        assert len(flavors)

        # Remove all versions and flavors of this name before adding this
        # package. This avoids flavor change issues by replacing all flavors.
        self.remove(name)

        plain = deps.parseFlavor('')
        x86 = deps.parseFlavor('is: x86')
        x86_64 = deps.parseFlavor('is: x86_64')

        if len(flavors) == 1:
            flavor = flavors[0]
            # noarch package, add unconditionally
            if flavor == plain:
                self.add(name, version=version)

            # x86, add with use=x86
            elif flavor.satisfies(x86):
                self.add(name, version=version, flavor=flavor, use='x86')

            # x86_64, add with use=x86_64
            elif flavor.satisfies(x86_64):
                self.add(name, version=version, flavor=flavor, use='x86_64')

            else:
                raise UnsupportedTroveFlavorError(name=name, flavor=flavor)

            return

        elif len(flavors) == 2:
            # This is most likely a normal package with both x86 and x86_64, but
            # lets make sure anyway.
            flvCount = {x86: 0, x86_64: 0, plain: 0}
            for flavor in flavors:
                if flavor.satisfies(x86):
                    flvCount[x86] += 1
                elif flavor.satisfies(x86_64):
                    flvCount[x86_64] += 1
                elif flavor.freeze() == '':
                    flvCount[plain] += 1
                else:
                    raise UnsupportedTroveFlavorError(name=name, flavor=flavor)

            # make sure there is only one instance of x86 and once instance of
            # x86_64 in the flavor list.
            assert (flvCount[x86_64] > 0) ^ (flvCount[plain] > 0)
            assert len([ x for x, y in flvCount.iteritems() if y != 1 ]) == 1

            # In this case just add the package unconditionally
            self.add(name, version=version)

            return

        # These are special cases.
        else:
            # The way I see it there are a few ways you could end up here.
            #    1. this is a kernel
            #    2. this is a kernel module
            #    3. this is a special package like glibc or openssl where there
            #       are i386, i686, and x86_64 varients.
            #    4. this is a package with package flags that I don't know
            #       about.
            # Lets see if we know about this package and think it should have
            # more than two flavors.


            # Get source trove name.
            log.info('retrieving trove info for %s' % name)
            srcTroveMap = self._helper._getSourceTroves(
                (name, version, flavors[0])
            )
            srcTroveName = srcTroveMap.keys()[0][0].split(':')[0]

            # handle kernels.
            if srcTroveName == 'kernel' or util.isKernelModulePackage(name):
                # add all x86ish flavors with use=x86 and all x86_64ish flavors
                # with use=x86_64
                for flavor in flavors:
                    if flavor.satisfies(x86):
                        self.add(name, version=version, flavor=flavor, use='x86')
                    elif flavor.satisfies(x86_64):
                        self.add(name, version=version, flavor=flavor, use='x86_64')
                    else:
                        raise UnsupportedTroveFlavorError(name=name,
                                                          flavor=flavor)

            # maybe this is one of the special flavors we know about.
            elif srcTroveName in self._cfg.packageFlavors:
                # separate packages into x86 and x86_64 by context name
                # TODO: If we were really smart we would load the conary
                #       contexts and see what buildFlavors they contained.
                flavorCount = {'x86': 0, 'x86_64': 0}
                for context, bldflv in self._cfg.packageFlavors[srcTroveName]:
                    if context in ('i386', 'i486', 'i586', 'i686', 'x86'):
                        flavorCount['x86'] += 1
                    elif context in ('x86_64', ):
                        flavorCount['x86_64'] += 1
                    else:
                        raise UnknownBuildContextError(name=name,
                                                       flavor=context)

                for flavor in flavors:
                    if flavor.satisfies(x86):
                        flavorCount['x86'] -= 1
                    elif flavor.satisfies(x86_64):
                        flavorCount['x86_64'] -= 1
                    else:
                        raise UnsupportedTroveFlavorError(name=name,
                                                          flavor=flavor)

                errors = [ x for x, y in flavorCount.iteritems() if y != 0 ]
                if errors:
                    raise FlavorCountMismatchError(name=name)

                for flavor in flavors:
                    if flavor.satisfies(x86):
                        self.add(name, version=version,
                                 flavor=flavor, use='x86')
                    elif flavor.satisfies(x86_64):
                        self.add(name, version=version,
                                 flavor=flavor, use='x86_64')
                    else:
                        raise UnsupportedTroveFlavorError(name=name,
                                                          flavor=flavor)
            return

        # Unknown state.
        raise UnhandledPackageAdditionError(name=name)

    @checkout
    def setVersion(self, version):
        """
        Set the version of the managed group.
        """

        self._helper.setVersion(self._sourceName, version)

    @checkout
    def setErrataState(self, state):
        """
        Set errata state info for the managed platform.
        """

        self._helper.setErrataState(self._sourceName, state)

    @checkout
    def getErrataState(self):
        """
        Get the errata state info.
        """

        return self._helper.getErrataState(self._sourceName)

    def getVersions(self, pkgSet):
        """
        Get the set of versions that are represented by the given set of
        packages from the version factory.
        """

        return set()
        #return self._versionFactory.getVersions(pkgSet)

    def _copyVersions(self):
        """
        Copy versions from the packages group to the other managed groups.
        """

        pkgs = dict([ (x[1].name, x[1]) for x in
                        self._groups[self._pkgGroupName].iteritems() ])

        for group in self._groups.itervalues():
            # skip over package group since it is the version source.
            if group.groupName == self._pkgGroupName:
                continue

            # for all other groups iterate over contents and set versions to
            # match package group.
            for k, pkg in group.iteritems():
                if pkg.name in pkgs:
                    pkg.version = pkgs[pkg.name].version
                else:
                    raise UnknownPackageFoundInManagedGroupError(what=pkg.name)

    def _validateGroups(self):
        """
        Validate the contents of the package group to ensure sanity:
            1. Check for packages that have the same source name, but
               different versions.
            2. Check that the version in the group is the latest source/build
               of that version.
            3. Check that package removals specified in the config file have
               occured.
        """

        errors = []
        for name, group in self._groups.iteritems():
            log.info('checking consistentcy of %s' % name)
            try:
                self._checkNameVersionConflict(group)
            except NameVersionConflictsFoundError, e:
                errors.append((group, e))

            try:
                self._checkLatestVersion(group)
            except OldVersionsFoundError, e:
                errors.append((group, e))

            try:
                self._checkRemovals(group)
            except ExpectedRemovalValidationFailedError, e:
                errors.append((group, e))

        if errors:
            raise GroupValidationFailedError(errors=errors)

    def _checkNameVersionConflict(self, group):
        """
        Check for packages taht have the same source name, but different
        versions.
        """

        # get names and versions
        troves = set()
        for pkgKey, pkgData in group.iteritems():
            name = str(pkgData.name)

            version = None
            if pkgData.version:
                version = str(versions.ThawVersion(pkgData.version).asString())

            flavor = None
            # FIXME: At some point we might want to add proper flavor handling,
            #        note that group flavor handling is different than what
            #        findTroves normally does.
            #if pkgData.flavor:
            #    flavor = deps.ThawFlavor(str(pkgData.flavor))

            troves.add((name, version, flavor))

        # Get flavors and such.
        foundTroves = set([ x for x in
            itertools.chain(*self._helper.findTroves(troves).itervalues()) ])

        # get sources for each name version pair
        sources = self._helper.getSourceVersions(foundTroves)

        seen = {}
        for (n, v, f), pkgSet in sources.iteritems():
            binVer = list(pkgSet)[1][1]
            seen.setdefault(n, set()).add(binVer)

        binPkgs = {}
        conflicts = {}
        for name, vers in seen.iteritems():
            if len(vers) > 1:
                log.error('found multiple versions of %s' % name)
                for binVer in vers:
                    srcVer = binVer.getSourceVersion()
                    nvf = (name, srcVer, None)
                    conflicts.setdefault(name, []).append(srcVer)
                    binPkgs[nvf] = sources[nvf]

        if conflicts:
            raise NameVersionConflictsFoundError(groupName=group.groupName,
                                                 conflicts=conflicts,
                                                 binPkgs=binPkgs)

    def _checkLatestVersion(self, group):
        """
        Check to make sure each specific conary version is the latest source
        and build count of the upstream version.
        """

        # get names and versions
        troves = set()
        for pkgKey, pkgData in group.iteritems():
            name = str(pkgData.name)

            version = None
            if pkgData.version:
                version = versions.ThawVersion(pkgData.version)
                # get upstream version
                revision = version.trailingRevision()
                upstreamVersion = revision.getVersion()

                # FIXME: This should probably be a fully formed version
                #        as above.
                version = upstreamVersion

            flavor = None
            # FIXME: At some point we might want to add proper flavor handling,
            #        note that group flavor handling is different than what
            #        findTroves normally does.
            #if pkgData.flavor:
            #    flavor = deps.ThawFlavor(str(pkgData.flavor))

            troves.add((name, version, flavor))

        # Get flavors and such.
        foundTroves = dict([ (x[0], y) for x, y in
            self._helper.findTroves(troves).iteritems() ])

        pkgs = {}
        for pkgKey, pkgData in group.iteritems():
            name = str(pkgData.name)
            version = None
            if pkgData.version:
                version = versions.ThawVersion(pkgData.version)
            flavor = None
            if pkgData.flavor:
                flavor = deps.ThawFlavor(str(pkgData.flavor))

            pkgs.setdefault(name, []).append((name, version, flavor))

        assert len(pkgs) == len(foundTroves)

        errors = {}
        for name, found in foundTroves.iteritems():
            assert name in pkgs
            current = pkgs[name]

            if len(current) > len(found):
                log.warn('found more packages in the model than in the '
                    'repository, assuming that multiversion policy will '
                    'catch this.')
                continue

            assert len(current) == 1 or len(found) == len(current)

            foundError = False
            for i, (n, v, f) in enumerate(found):
                if len(current) == 1:
                    i = 0
                cn, cv, cf = current[i]
                assert n == cn

                if v != cv:
                    foundError = True

            if foundError:
                log.error('found old version for %s' % name)
                errors[name] = (current, found)

        if errors:
            raise OldVersionsFoundError(pkgNames=errors.keys(), errors=errors)

    def _checkRemovals(self, group):
        """
        Check to make sure that all configured package removals have happened.
        """

        updateId = self.getErrataState()

        # get package removals from the config object.
        removePackages = self._cfg.updateRemovesPackages.get(updateId, [])
        removeObsoleted = self._cfg.removeObsoleted.get(updateId, [])

        # take the union
        removals = set(removePackages) | set(removeObsoleted)

        errors = []
        # Make sure these packages are not in the group model.
        for pkgKey, pkgData in group.iteritems():
            if pkgData.name in removals:
                errors.append(pkgData.name)

        if errors:
            raise ExpectedRemovalValidationFailedError(updateId=updateId,
                                                       pkgNames=errors)


class GroupHelper(ConaryHelper):
    """
    Modified conary helper to deal with managing group sources.
    """

    def __init__(self, cfg):
        ConaryHelper.__init__(self, cfg)
        self._configDir = cfg.configPath
        self._newPkgFactory = 'managed-group'
        self._groupContents = cfg.groupContents

        # FIXME: autoLoadRecipes causes group versioning to go sideways
        # The group super class in the repository has a version defined, which
        # overrides the version from factory-version. This should probably be
        # considered a bug in factory-managed-group, but we don't need
        # autoLoadRecipes here anyway.
        self._ccfg.autoLoadRecipes = []

    def getModel(self, pkgName, version=None):
        """
        Get a thawed data representation of the group xml data from the
        repository.
        """

        log.info('loading model for %s' % pkgName)
        recipeDir = self._edit(pkgName, version=version)
        groupFileName = util.join(recipeDir, 'groups.xml')

        # load group model
        groups = {}
        if os.path.exists(groupFileName):
            model = GroupModel.thaw(groupFileName)
            for name, groupObj in model.iteritems():
                contentFileName = util.join(recipeDir, groupObj.filename)
                contentsModel = GroupContentsModel.thaw(contentFileName,
                                (name, groupObj.byDefault, groupObj.depCheck))
                contentsModel.fileName = groupObj.filename
                groups[groupObj.name] = contentsModel

        # copy in any group data
        for name, data in self._groupContents.iteritems():
            newGroups = [ x for x in groups.itervalues()
                            if x.groupName == name and
                               x.fileName == data['filename'] ]

            assert len(newGroups) in (0, 1)

            byDefault = data['byDefault'] == 'True' and True or False
            depCheck = data['depCheck'] == 'True' and True or False

            # load model
            contentsModel = GroupContentsModel.thaw(
                util.join(self._configDir, data['filename']),
                (name, byDefault, depCheck)
            )

            # override anything from the repo, unless retriveing a
            # specific version.
            if version is None:
                groups[name] = contentsModel

        return groups

    def setModel(self, pkgName, groups):
        """
        Freeze group model and save to the repository.
        """

        log.info('saving model for %s' % pkgName)
        recipeDir = self._edit(pkgName)
        groupFileName = util.join(recipeDir, 'groups.xml')

        groupModel = GroupModel()
        for name, model in groups.iteritems():
            groupfn = util.join(recipeDir, model.fileName)

            model.freeze(groupfn)
            groupModel.add(name=name,
                           filename=model.fileName,
                           byDefault=model.byDefault,
                           depCheck=model.depCheck)
            self._addFile(recipeDir, model.fileName)

        groupModel.freeze(groupFileName)
        self._addFile(recipeDir, 'groups.xml')

    def getErrataState(self, pkgname, version=None):
        """
        Get the contents of the errata state file from the specified package,
        if file does not exist, return None.
        """

        log.info('getting errata state information from %s' % pkgname)

        recipeDir = self._edit(pkgname, version=version)
        stateFileName = util.join(recipeDir, 'erratastate')

        if not os.path.exists(stateFileName):
            return None

        state = open(stateFileName).read().strip()
        if state.isdigit():
            state = int(state)
        return state

    def setErrataState(self, pkgname, state):
        """
        Set the current errata state for the given package.
        """

        log.info('storing errata state information in %s' % pkgname)

        recipeDir = self._edit(pkgname)
        stateFileName = util.join(recipeDir, 'erratastate')

        # write state info
        statefh = open(stateFileName, 'w')
        statefh.write(str(state))

        # source files must end in a trailing newline
        statefh.write('\n')

        statefh.close()

        # make sure state file is part of source trove
        self._addFile(recipeDir, 'erratastate')


class AbstractModel(object):
    """
    Base object for models.
    """

    docClass = None
    dataClass = None
    elementClass = None

    def __init__(self):
        self._data = {}
        self._nameMap = {}

    def _addItem(self, item):
        """
        Add an item to the appropriate structures.
        """

        self._data[item.key] = item
        if item.name not in self._nameMap:
            self._nameMap[item.name] = set()
        self._nameMap[item.name].add(item.key)

    def _removeItem(self, name):
        """
        Remove an item from the appropriate structures.
        """

        keys = self._nameMap.pop(name)
        for key in keys:
            self._data.pop(key)

    @classmethod
    def thaw(cls, xmlfn, args=None):
        """
        Thaw the model from xml.
        """

        model = cls.docClass.fromfile(xmlfn)
        obj = args and cls(*args) or cls()
        for item in model.data.items:
            obj._addItem(item)
        return obj

    def freeze(self, toFile):
        """
        Freeze the model to a given output file.
        """

        def _srtByKey(a, b):
            return cmp(a.key, b.key)

        model = self.dataClass()
        model.items = sorted(self._data.values(), cmp=_srtByKey)

        doc = self.docClass()
        doc.data = model
        doc.tofile(toFile)

    def iteritems(self):
        """
        Iterate over the model data.
        """

        return self._data.iteritems()

    def add(self, *args, **kwargs):
        """
        Add an data element.
        """

        obj = self.elementClass(*args, **kwargs)
        self._addItem(obj)

    def remove(self, name):
        """
        Remove data element.
        """

        self._removeItem(name)


class GroupModel(AbstractModel):
    """
    Model for representing group name and file name.
    """

    docClass = XGroupDoc
    dataClass = XGroupList
    elementClass = XGroup


class GroupContentsModel(AbstractModel):
    """
    Model for representing group data.
    """

    docClass = XPackageDoc
    dataClass = XPackageData
    elementClass = XPackageItem

    def __init__(self, groupName, byDefault=True, depCheck=True):
        AbstractModel.__init__(self)
        self.groupName = groupName
        self.byDefault = byDefault
        self.depCheck = depCheck

        # figure out file name based on group name
        name = ''.join([ x.capitalize() for x in self.groupName.split('-') ])
        self.fileName = name[0].lower() + name[1:] + '.xml'


class URLVersionSource(object):
    """
    Class for handling the indexing and comparison of ISO contents.
    """

    def __init__(self, cfg, version, url):
        self._cfg = cfg
        self._version = version
        self._url = url

        pkgSource = RpmSource(cfg, )
        pkgSource.loadFromUrl(url)
        pkgSource.finalize()
        pkgSource.setLoaded()

        self._sourceSet = set([ x for x in pkgSource.iterPackageSet() ])

    def areWeHereYet(self, pkgSet):
        """
        Figure out if the given package set is this version.
        @param pkgSet: set of source names and source versions
        @type pkgSet: set([(conarySourceName, conarySourceVersion)])
        @return boolean
        """

        # Make sure that all versions that are on the ISO are in the conary
        # repository. It appears to be a common case that the ISO is missing
        # content from RHN.
        return not self._sourceSet.difference(pkgSet)


class VersionFactory(object):
    """
    Class for generating group verisons from a variety of sources.
    """

    def __init__(self, cfg):
        self._cfg = copy.deepcopy(cfg)
        self._cfg.synthesizeSources = True
        self._sources = {}

        for version, url in sorted(cfg.versionSources.iteritems()):
            self._sources[version] = URLVersionSource(self._cfg, version, url)

    def getVersions(self, pkgSet):
        """
        Given the available package sources find the current versions.
        """

        versions = []
        for version, source in sorted(self._sources.iteritems()):
            if source.areWeHereYet(pkgSet):
                versions.append(version)
        return set(versions)
