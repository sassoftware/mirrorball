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

    def __init__(self, cfg, ui):
        self._cfg = cfg
        self._ui = ui
        self._mgrs = {}

    def newGroup(self, name):
        """
        Create a new group manager instance with the provided name.
        """

        assert name not in self._mgrs
        mgr = self._managerClass(name, self._cfg, self._ui)
        self._mgrs[name] = mgr
        return mgr

    def commit(self):
        """
        Commit latest group in all managers.
        """

        for mgr in self._mgrs.itervalues():
            mgr.latest.commit()

    def build(self):
        """
        Build all groups in the set.
        """

        # Make sure there are groups defined
        assert self._mgrs

        pkgMap = {}
        for mgr in self._mgrs.itervalues():
            pkgMap.update(mgr.latest.build())

        return pkgMap

    def hasGroups(self):
        """
        Add method for checking if a manager has any groups defined.
        """

        return bool(self._mgrs)
