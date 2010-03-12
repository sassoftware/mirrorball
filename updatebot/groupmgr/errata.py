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
Module for managing errata groups.
"""

from updatebot.groupmgr.single import SingleGroupHelper
from updatebot.groupmgr.single import SingleGroupManager
from updatebot.groupmgr.single import SingleGroupManagerSet

class ErrataGroupHelper(SingleGroupHelper):
    """
    Class for managing errata group source troves.
    """

    def __init__(self, *args, **kwargs):
        SingleGroupHelper.__init__(self, *args, **kwargs)
        self._newPkgFactory = 'managed-errata-group'


class ErrataGroupManager(SingleGroupManager):
    """
    Class for managing errata group model.
    """

    _helperClass = ErrataGroupHelper


class ErrataGroupManagerSet(SingleGroupManagerSet):
    """
    Class for managing a set of errata groups.
    """

    _managerClass = ErrataGroupManager
