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
Module for managing groups that contain only packages with no subgroups.
"""

from updatebot.groupmgr.helper import GroupHelper
from updatebot.groupmgr.manager import GroupManager

class SingleGroupHelper(GroupHelper):
    """
    Group helper for managing groups with only packages and no other groups.
    """

    def __init__(self, *args, **kwargs):
        GroupHelper.__init__(self, *args, **kwargs)
        self._groupContents = {}


class SingleGroupManager(GroupManager):
    """
    Class to manage a single group that contains only packages with no
    subgroups.
    """

    _helperClass = SingleGroupHelper

    def __init__(self, name, *args, **kwargs):
        GroupManager.__init__(self, *args, **kwargs)
        self._sourceName = 'group-%s:source' % name
        self._pkgGroupName = 'group-%s' % name


class SingleGroupManagerSet(object):
    """
    Class for working with a set of group manager instances.
    """

    _managerClass = SingleGroupManager

    def __init__(self, cfg):
        self._cfg = cfg
        self._groups = {}

    def newGroup(self, name):
        """
        Create a new group instance with the provided name.
        """

        assert name not in self._groups
        group = self._managerClass(name, self._cfg)
        self._groups[name] = group
        return group

    def build(self):
        """
        Build all groups in the set.
        """

        # Make sure there are groups defined
        assert self._groups

        pkgMap = {}
        for group in self._groups.itervalues():
            pkgMap.update(group.buildGroup(group.latest))

        return pkgMap

    def hasGroups(self):
        """
        Add method for checking if a manager has any groups defined.
        """

        return bool(self._groups)
