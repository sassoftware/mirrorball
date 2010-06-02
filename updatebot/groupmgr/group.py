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
Module for modeling the contents of a top level group.
"""

import logging

from conary.deps import deps

from updatebot.errors import FlavorCountMismatchError
from updatebot.errors import UnknownBuildContextError
from updatebot.errors import UnsupportedTroveFlavorError
from updatebot.errors import UnhandledPackageAdditionError
from updatebot.errors import UnknownPackageFoundInManagedGroupError

from updatebot.groupmgr.model import GroupContentsModel

log = logging.getLogger('updatebot.groupmgr')

def require_write(func):
    def wrapper(self, *args, **kwargs):
        if not hasattr(self, '_readOnly'):
            log.warn('instance has no attribute _readOnly, assuming writable')
            readOnly = True
        else:
            readOnly = self._readOnly

        if readOnly:
            raise RuntimeError, 'This group is marked as readonly.'
        else:
            self._dirty = True
            return func(self, *args, **kwargs)
    return wrapper

def enforce_readonly(attr):
    def set(self, value):
        if self._readOnly:
            raise RuntimeError, 'This attribute is marked as read only.'
        else:
            self._dirty = True
            setattr(self, attr, value)
    def get(self):
        return getattr(self, attr)
    return property(get, set)


class Group(object):
    """
    Class for managing group contents.
    """

    def __init__(self, cfg, useMap, sanityChecker, groupmgr, pkgGroupName,
        groups, errataState, version, conaryVersion):
        self._cfg = cfg
        self._groups = groups
        self._useMap = useMap
        self._sanity = sanityChecker
        self._mgr = groupmgr

        self._pkgGroupName = pkgGroupName

        self._errataState = errataState
        self._version = version
        self._conaryVersion = conaryVersion

        self._dirty = False
        self._committed = False
        self._readOnly = False

    errataState = enforce_readonly('_errataState')
    version = enforce_readonly('_version')
    conaryVersion = enforce_readonly('_conaryVersion')

    def setReadOnly(self):
        """
        Make this group read only.
        """

        self._readOnly = True

    @property
    def dirty(self):
        """
        Check if an instance has been modified in some way.
        """

        return self._dirty

    @property
    def committed(self):
        """
        Check if an instances has been marked as committed.
        """

        return self._committed or not self._dirty

    def setCommitted(self):
        """
        Mark this group as committed.
        """

        self._dirty = False
        self._committed = True

    def __hash__(self):
        """
        Make groups hashable.
        """

        return hash(self._conaryVersion)

    def __cmp__(self, other):
        """
        Compare groups to other groups.
        """

        return cmp(self._conaryVersion, other._conaryVersion)

    def __iter__(self):
        """
        Iterate over group model instances.
        """

        return self._groups.itervalues()

    def iteritems(self):
        """
        Iterate over groupName, groupModel pairs.
        """

        return self._groups.iteritems()

    ###
    # Start of group manager interface
    #
    # Since we sever any relation between the group manager and group instance
    # at commit time we should avoid the circular reference loop.
    ###

    def commit(self, copyToLatest=False):
        """
        Save this group to the repository.
        """

        return self._mgr.setGroup(self, copyToLatest=copyToLatest)

    def build(self):
        """
        Build this group.
        """

        return self._mgr.buildGroup(self)

    def hasBinaryVersion(self):
        """
        Check if this group has a binary version.
        """

        return self._mgr.hasBinaryVersion(sourceVersion=self.conaryVersion)

    ###
    # end group manager interface
    ###

    @require_write
    def _add(self, *args, **kwargs):
        """
        Add a trove to the package group contents.
        """

        groupName = kwargs.pop('groupName', self._pkgGroupName)

        # create package group model if it does not exist.
        if groupName not in self._groups:
            self._groups[groupName] = GroupContentsModel(groupName)

        self._groups[groupName].add(*args, **kwargs)

    @require_write
    def addPackage(self, name, version, flavors, groupName=None):
        """
        Add a package to the model.
        @param name: name of the package
        @type name: str
        @param version: conary version from string object
        @type version: conary.versions.VersionFromString
        @param flavors: list of flavors
        @type flavors: [conary.deps.deps.Flavor, ...]
        """

        if not groupName:
            groupName = self._pkgGroupName

        # Now that versions are actually used for something make sure they
        # are always present.
        if groupName == self._pkgGroupName:
            assert version
        assert len(flavors)
        flavors = list(flavors)

        # Remove all versions and flavors of this name before adding this
        # package. This avoids flavor change issues by replacing all flavors.
        if self.hasPackage(name):
            self.removePackage(name)

        plain = deps.parseFlavor('')
        x86 = deps.parseFlavor('is: x86')
        x86_64 = deps.parseFlavor('is: x86_64')
        biarch = deps.parseFlavor('is: x86 x86_64')

        # Count the flavors for later use.
        flvMap = {}
        flvCount = {x86: 0, x86_64: 0, plain: 0, biarch: 0}
        for flavor in flavors:
            # NOTE: Biarch must come first since a biarch flavored binary also
            #       saitisfies both x86 and x86_64.
            if flavor.satisfies(biarch):
                flvCount[biarch] += 1
                flvMap[flavor] = 'x86_64'
            elif flavor.satisfies(x86):
                flvCount[x86] += 1
                flvMap[flavor] = 'x86'
            elif flavor.satisfies(x86_64):
                flvCount[x86_64] += 1
                flvMap[flavor] = 'x86_64'
            elif flavor.freeze() == '':
                flvCount[plain] += 1
                flvMap[flavor] = None
            else:
                raise UnsupportedTroveFlavorError(name=name, flavor=flavor)

        def add():
            upver = version.trailingRevision().version
            for flv in flavors:
                primary = (name, upver, flvMap[flv])
                secondary = (name, flvMap[flv])
                use = self._useMap.get(primary, self._useMap.get(secondary, []))
                if use:
                    for useStr in use:
                        self._add(name, version=version, flavor=flv,
                                  use=useStr, groupName=groupName)
                else:
                    log.warn('%s=%s[%s] not found in useMap, falling back to '
                             'old method of adding troves to groups'
                             % (name, version, flvMap[flv]))
                    self._add(name, version=version, flavor=flv,
                              use=flvMap[flv], groupName=groupName)

        # If this package has one or two flavors and one of those flavors is
        # x86, x86_64, biarch, or plain then handle it like a normal package
        # without doing any more sanity checking.
        total = 0
        for flv, count in flvCount.iteritems():
            if count > 1:
                break
            total += count
        else:
            if total in (1, 2, 3):
                add()
                return

        # Handle all other odd flavor cases:
        #   1. kernels
        #   2. kernel modules
        #   3. packages with specifically defined flavor sets

        # Check if this package is configured to have multiple flavors.
        # Get source trove name.
        log.info('retrieving trove info for %s' % name)
        srcTroveMap = self._mgr._helper._getSourceTroves((name, version, flavors[0]))
        srcTroveName = srcTroveMap.keys()[0][0].split(':')[0]

        # Check if this is package that we have specifically defined a build
        # flavor for.
        if srcTroveName in self._cfg.packageFlavors:
            # separate packages into x86 and x86_64 by context name
            # TODO: If we were really smart we would load the conary
            #       contexts and see what buildFlavors they contained.
            flavorCtxCount = {x86: 0, x86_64: 0, biarch: 0}
            ctxMap = dict([ (x, y[1]) for x, y in self._cfg.archContexts if y ])
            for context, bldflv in self._cfg.packageFlavors[srcTroveName]:
                fltr = ctxMap.get(context, None)
                if context in ('i386', 'i486', 'i586', 'i686', 'x86'):
                    flavorCtxCount[x86] += 1
                elif context in ('x86_64', ):
                    flavorCtxCount[x86_64] += 1
                elif context in ('biarch', ):
                    if fltr and fltr.match(name):
                        flavorCtxCount[biarch] += 1
                else:
                    raise UnknownBuildContextError(name=name, flavor=context)

            # Sanity check flavors to make sure we built all the flavors
            # that we expected.
            if (flvCount[x86] != flavorCtxCount[x86] or
                flvCount[x86_64] != flavorCtxCount[x86_64] or

                # Only enforce biarch for packages that we expect to be biarch.
                # This is a kluge to deal with the fact that biarch builds
                # produce a byDefault=False package for the source that only
                # contains the build log.
                (flavorCtxCount[biarch] > 0 and
                 flvCount[biarch] != flavorCtxCount[biarch])):
                raise FlavorCountMismatchError(name=name)

            # Add packages to the group.
            add()
            return

        # handle kernels.
        if srcTroveName == 'kernel' or srcTroveName in self._cfg.kernelModules:
            # add all x86ish flavors with use=x86 and all x86_64ish flavors
            # with use=x86_64
            for flavor in flavors:
                if flvMap[flavor] in ('x86', 'x86_64'):
                    self._add(name, version=version, flavor=flavor,
                             use=flvMap[flavor], groupName=groupName)
                else:
                    raise UnsupportedTroveFlavorError(name=name, flavor=flavor)
            return

        # don't know how to deal with this package.
        raise UnhandledPackageAdditionError(name=name)

    @require_write
    def removePackage(self, name, missingOk=False):
        """
        Remove a given trove from the package group contents.
        """

        if self._pkgGroupName not in self._groups:
            return

        return self._groups[self._pkgGroupName].remove(name,
             missingOk=missingOk)

    def hasPackage(self, name):
        """
        Check if a given package name is in the group.
        """

        return (self._pkgGroupName in self._groups and
                name in self._groups[self._pkgGroupName])

    __contains__ = hasPackage

    @require_write
    def modifyContents(self, additions=None, removals=None):
        """
        Modify the contents of the group model by adding and/or removing
        packages.
        @param additions: dictionary of group names to add packages to.
        @type additions: dict(groupName=[(pkgName, frzPkgFlavor), ...])
        @param removals: dictionary of group names to remove packages from.
        @type additions: dict(groupName=[(pkgName, frzPkgFlavor), ...])
        """

        if additions is None:
            additions = {}
        if removals is None:
            removals = {}

        # 1. Apply removals before additions in case we are changing flavors
        # 2. If flavor is specified, only modify that single flavor, otherwise
        #    following normal addition rules as stated in addPackage.

        # Remove requested packages.
        for groupName, pkgs in removals.iteritems():
            group = self._groups[groupName]
            for pkgName, pkgFlv in pkgs:
                if pkgFlv:
                    group.removePackageFlavor(pkgName, pkgFlv.freeze())
                else:
                    group.remove(pkgName)

        # Add requested packages.
        for groupName, pkgs in additions.iteritems():
            if groupName == self._pkgGroupName:
                log.warn('modifyContents does not support modifying the package'
                         'group, please update your config file')
                continue

            flavoredPackages = {}
            for pkgName, pkgFlv in pkgs:
                # deffer packages with specifc flavors for later.
                if pkgFlv is not None:
                    flavoredPackages.setdefault(pkgName, set()).add(pkgFlv)

                # handle packages where flavor is not specified
                else:
                    # copy packages from the packages group.
                    for pkg in self._groups[self._pkgGroupName]:
                        if pkg.name == pkgName:
                            self._add(pkg.name, version=None,
                                      flavor=pkg.flavor, use=pkg.use,
                                      groupName=groupName)

            # Add all specifically flavored packages.
            for pkgName, flavors in flavoredPackages.iteritems():
                for flv in flavors:
                    self._add(pkgName, version=None, flavor=flv, use=None,
                              groupName=groupName)

    @require_write
    def _copyVersions(self):
        """
        Copy versions from the packages group to the other managed groups.
        """

        # Get the versions of all packge names.
        pkgs = dict([ (x.name, x) for x in self._groups[self._pkgGroupName] ])

        for group in self:
            # skip over package group since it is the version source.
            if group.groupName == self._pkgGroupName:
                continue

            # for all other groups iterate over contents and set versions to
            # match package group.
            for pkg in group:
                if pkg.name in pkgs:
                    pkg.version = pkgs[pkg.name].version
                else:
                    raise UnknownPackageFoundInManagedGroupError(what=pkg.name)

    def _sanityCheck(self):
        """
        Validate the group contents. This will raise an exception if any errors
        are found.
        """

        self._sanity.check(self._groups, self.errataState)

    def _setGroupFlags(self):
        """
        Set flags on the group based on the groupContents configuration.
        """

        for groupName, groupObj in self._groups.iteritems():
            for key, value in self._cfg.groupContents.get(groupName, []):
                 value = value == 'True' and True or False
                 setattr(groupObj, key, value)

    @require_write
    def finalize(self):
        """
        Handle any steps to prepair the group model before saving to disk.
        """

        # Copy versions from the package group to all other groups.
        self._copyVersions()

        # Check the sanity of all group models.
        self._sanityCheck()

        # Make sure flags on the group match the config.
        self._setGroupFlags()

        # Make as readonly.
        self.setReadOnly()
