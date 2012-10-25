#
# Copyright (c) rPath, Inc.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
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
