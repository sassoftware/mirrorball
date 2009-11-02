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

import logging

from updatebot.lib import util
from updatebot.build import Builder
from updatebot.conaryhelper import ConaryHelper

from updatebot.lib.xobjects import XGroup
from updatebot.lib.xobjects import XGroupList
from updatebot.lib.xobjects import XPackageData
from updatebot.lib.xobjects import XPackageItem

log = logging.getLogger('updatebot.groupmgr')

class GroupManager(object):
    """
    Manage group of all packages for a platform.
    """

    def __init__(self, cfg):
        self._cfg = cfg
        self._helper = GroupHelper(self._cfg)
        self._builder = Builder(self._cfg, rmakeCfgFn='rmakerc-groups')

        self._sourceName = self._cfg.topSourceGroup[0]

        self._dirty = False

        self._groups = {} 

    def checkout(self):
        """
        Get current group state from the repository.
        """

        # Checkout or create the source trove
        self._groups = self._helper.getModel(sel._sourceName)

    def commit(self):
        """
        Commit current changes to the group.
        """

        # 1. checkout current group
        # 2. copy external group descriptions (group-$platform-platform) if
        #    description has changed.
        # 3. freeze model
        # 4. commit changes

    def build(self):
        """
        Build all configured flavors of the group.
        """

        # build groups

    def update(self, trvList):
        """
        Modify list of troves in a group.
        """

        # add/update version in model


class GroupHelper(ConaryHelper):
    """
    Modified conary helper to deal with managing group sources.
    """

    def __init__(self, cfg):
        ConaryHelper.__init__(self, cfg)
        self._newPkgFactory = 'managed-group'
        self._configDir = cfg.configPath

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
                contentFileName = util.join(recipeDir, groupObj.filename)
                contentsModel = GroupContentsModel.thaw(contentFileName)
                contentsModel.groupName = groupObj.name
                contentsModel.fileName = groupObj.filename
                groups[groupObj.name] = contentsModel

        # copy in any group data
        for gData in os.listdir(self._configDir):
            if not gData.endswith('.xml'):
                continue

            contentsModel = GroupContentsModel.thaw(
                util.join(self._configDir, gData))
            

class AbstractModel(object):
    """
    Base object for models.
    """

    dataClass = None

    def __init__(self):
        self._data = {}
        self._hash = None

    def __hash__(self):
        if not self._hash:
            raise RuntimeError
        return self._hash

    def __cmp__(self, other):
        return cmp(self._hash, other._hash)

    @classmethod
    def thaw(cls, xmlfn):
        """
        Thaw the model from xml.
        """

        xml = open(xmlfn).read()
        hash = hashlib.sha1(xml).hexdigest()
        mode = self.dataClass.thaw(xml)
        obj = cls()
        obj._hash = hash
        for item in model.items:
            self._data[item.name] = item

    def freeze(self, toFile):
        """
        Freeze the model to a given output file.
        """

        model = XGroupList()
        model.items = self._data.values()
        model.freeze(toFile)

    def iteritems(self):
        """
        Iterate over the model data.
        """

        return self._data.iteritems()

class GroupModel(AbstractModel):
    """
    Model for representing group name and file name.
    """

    dataClass = XGroupList


class GroupContentsModel(AbstractModel):
    """
    Model for representing group data.
    """

    dataClass = XPackageData

    def __init__(self, groupName):
        AbstractModel.__init__(self)
        self.groupName = groupName

        # figure out file name based on group name
        name = ''.join([ x.capitalize() for x in self.groupName.split('-') ])
        self.fileName = name[0].lower() + name[1:]

    def update(self, trvList):
        """
        Modify list of troves in a group.
        """
