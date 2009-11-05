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
import logging

from conary.deps import deps

from updatebot.lib import util
from updatebot.build import Builder
from updatebot.conaryhelper import ConaryHelper
from updatebot.lib.xobjects import XGroup
from updatebot.lib.xobjects import XGroupDoc
from updatebot.lib.xobjects import XGroupList
from updatebot.lib.xobjects import XPackageDoc
from updatebot.lib.xobjects import XPackageData
from updatebot.lib.xobjects import XPackageItem
from updatebot.errors import FlavorCountMismatchError
from updatebot.errors import UnknownBuildContextError
from updatebot.errors import UnsupportedTroveFlavorError
from updatebot.errors import UnhandledPackageAdditionError

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

        self._sourceName = self._cfg.topSourceGroup[0]
        self._sourceVersion = self._cfg.topSourceGroup[1]

        self._pkgGroupName = 'group-%s-packages' % self._cfg.platformName

        self._checkedout = False
        self._groups = {}

    def _checkout(self):
        """
        Get current group state from the repository.
        """

        self._groups = self._helper.getModel(self._sourceName)
        self._checkedout = True

    def _commit(self):
        """
        Commit current changes to the group.
        """

        self._helper.setModel(self._sourceName, self._groups)
        self._checkedout = False

    save = _commit

    @commit
    def build(self):
        """
        Build all configured flavors of the group.
        """

        # create list of trove specs to build
        groupTroves = set()
        for flavor in self._cfg.groupFlavors:
            groupTroves.add((self._sourceName, self._sourceVersion, flavor))

        built = self._builder.build(groupTroves)
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

        add = self._groups[self._pkgGroupName].add(*args, **kwargs)

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

        assert len(flavors)

        plain = deps.parseFlavor('')
        x86 = deps.parseFlavor('is: x86')
        x86_64 = deps.parseFlavor('is: x86_64')

        if len(flavors) == 1:
            flavor = flavors[0]
            # noarch package, add unconditionally
            if flavor == plain:
                self.add(name)

            # x86, add with use=x86
            elif flavor.satisfies(x86):
                self.add(name, flavor=flavor, use='x86')

            # x86_64, add with use=x86_64
            elif flavor.satisfies(x86_64):
                self.add(name, flavor=flavor, use='x86_64')

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
            self.add(name)

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
                        self.add(name, flavor=flavor, use='x86')
                    elif flavor.satisfies(x86_64):
                        self.add(name, flavor=flavor, use='x86_64')
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
                        self.add(name, flavor=flavor, use='x86')
                    elif flavor.satisfies(x86_64):
                        self.add(name, flavor=flavor, use='x86_64')
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

        self._helper.getErrataState(self._sourceName)


class GroupHelper(ConaryHelper):
    """
    Modified conary helper to deal with managing group sources.
    """

    def __init__(self, cfg):
        ConaryHelper.__init__(self, cfg)
        self._configDir = cfg.configPath
        self._newPkgFactory = 'managed-group'
        self._groupContents = cfg.groupContents

    def getModel(self, pkgName):
        """
        Get a thawed data representation of the group xml data from the
        repository.
        """

        log.info('loading model for %s' % pkgName)
        recipeDir = self._edit(pkgName)
        groupFileName = util.join(recipeDir, 'groups.xml')

        # load group model
        groups = {}
        if os.path.exists(groupFileName):
            model = GroupModel.thaw(groupFileName)
            for name, groupObj in model.iteritems():
                contentFileName = util.join(recipeDir, groupObj.fileName)
                contentsModel = GroupContentsModel.thaw(contentFileName,
                                (name, groupObj.byDefault, groupObj.depCheck))
                contentsModel.fileName = groupObj.fileName
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

            # override anything from the repo
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
            groupModel.add(name, model.fileName)
            self._addFile(recipeDir, model.fileName)

        groupModel.freeze(groupFileName)
        self._addFile(recipeDir, 'groups.xml')

        #self._commit(recipeDir, commitMessage='automated group update')

    def getErrataState(self, pkgname):
        """
        Get the contents of the errata state file from the specified package,
        if file does not exist, return None.
        """

        log.info('getting errata state information from %s' % pkgname)

        recipeDir = self._edit(pkgname)
        stateFileName = util.join(recipeDir, 'erratastate')

        if not os.path.exists(stateFileName):
            return None

        state = open(stateFileName).read().strip()
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
        statefh.write(state)
        statefh.close()

        # make sure state file is part of source trove
        self._adFile('erratastate')


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

        model = self.dataClass()
        model.items = self._data.values()

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
