#
# Copyright (c) 2009-2010 rPath, Inc.
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

import logging
import itertools

from conary.deps import deps

from updatebot.lib import util
from updatebot.build import Builder

from updatebot.errors import FlavorCountMismatchError
from updatebot.errors import UnknownBuildContextError
from updatebot.errors import UnsupportedTroveFlavorError
from updatebot.errors import UnhandledPackageAdditionError
from updatebot.errors import NotCommittingOutOfDateSourceError
from updatebot.errors import UnknownPackageFoundInManagedGroupError

from updatebot.groupmgr.helper import GroupHelper
from updatebot.groupmgr.sanity import GroupSanityChecker
from updatebot.groupmgr.model import GroupContentsModel

log = logging.getLogger('updatebot.groupmgr')

def checkout(func):
    def wrapper(self, *args, **kwargs):
        if not self._checkedout:
            self._checkout()

        return func(self, *args, **kwargs)
    return wrapper

def commit(func):
    def wrapper(self, *args, **kwargs):
        if self._readonly:
            return

        if self._checkedout:
            self._commit()

        return func(self, *args, **kwargs)
    return wrapper


class GroupManager(object):
    """
    Manage group of all packages for a platform.
    """

    _helperClass = GroupHelper
    _sanityCheckerClass = GroupSanityChecker

    def __init__(self, cfg, parentGroup=False, targetGroup=False):
        self._cfg = cfg
        self._helper = self._helperClass(self._cfg)
        self._builder = Builder(self._cfg, rmakeCfgFn='rmakerc-groups')
        self._sanity = self._sanityCheckerClass(self._cfg, self._helper)

        assert not (parentGroup and targetGroup)

        if targetGroup:
            srcName = '%s:source' % self._cfg.topSourceGroup[0]
            trvs = self._helper.findTrove(
                (srcName, self._cfg.targetLabel, None))

            assert len(trvs)

            self._sourceName = self._cfg.topSourceGroup[0]
            self._sourceVersion = trvs[0][1]
            self._readonly = True
        elif parentGroup:
            topGroup = list(self._cfg.topParentSourceGroup)
            topGroup[0] = '%s:source' % topGroup[0]
            trvs = self._helper.findTrove(tuple(topGroup),
                    labels=self._cfg.platformSearchPath)

            assert len(trvs)

            self._sourceName = self._cfg.topParentSourceGroup
            self._sourceVersion = trvs[0][1]

            self._readonly = True
        else:
            self._sourceName = self._cfg.topSourceGroup[0]
            self._sourceVersion = None
            self._readonly = False

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
            version = self._helper.getVersion(self._sourceName,
                                              version=self._sourceVersion)
            errataState = self._helper.getErrataState(self._sourceName,
                                              version=self._sourceVersion)
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
        self._sanity.check(self._groups, self.getErrataState())

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

    def hasBinaryVersion(self, version=None):
        """
        Check if there is a binary version for the current source version.
        """

        if not version:
            verison = self._sourceVersion

        # Search the label from the source version.
        if self._sourceVersion:
            labels = (self._sourceVersion.trailingLabel(), )
        else:
            labels = (self._helper.getConaryConfig().buildLabel, )

        # Get a mapping of all source version to binary versions for all
        # existing binary versions.
        srcVersions = dict([ (x[1].getSourceVersion(), x[1])
            for x in self._helper.findTrove(
                (self._sourceName, None, None),
                getLeaves=False,
                labels=labels,
            )
        ])

        # Get the version of the specified source, usually the latest
        # source version.
        srcVersion = self._helper.findTrove(
            ('%s:source' % self._sourceName, version, None),
            labels=labels)

        if not srcVersion:
            return False

        # Check to see if the latest source version is in the map of
        # binary versions.
        return srcVersion[0][1] in srcVersions

    @commit
    def getBuildJob(self):
        """
        Get the list of trove specs to submit to the build system.
        """

        return ((self._sourceName, self._sourceVersion, None), )

    @checkout
    @commit
    def build(self):
        """
        Build all configured flavors of the group.
        """

        groupTroves = self.getBuildJob()
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
    def remove(self, name, missingOk=False):
        """
        Remove a given trove from the package group contents.
        """

        if self._pkgGroupName not in self._groups:
            return

        return self._groups[self._pkgGroupName].remove(name,
             missingOk=missingOk)

    @checkout
    def hasPackage(self, name):
        """
        Check if a given package name is in the group.
        """

        return (self._pkgGroupName in self._groups and
                name in self._groups[self._pkgGroupName])

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
        flavors = list(flavors)

        # Remove all versions and flavors of this name before adding this
        # package. This avoids flavor change issues by replacing all flavors.
        if self.hasPackage(name):
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
    def getErrataState(self, version=None):
        """
        Get the errata state info.
        """

        if version is None:
            version = self._sourceVersion

        return self._helper.getErrataState(self._sourceName,
                                           version=version)

    def getVersions(self, pkgSet):
        """
        Get the set of versions that are represented by the given set of
        packages from the version factory.
        """

        return set()

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
