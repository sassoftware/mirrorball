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
Module for doing updates ordered by errata information.
"""

import logging

from updatebot import errata
from updatebot.bot import Bot as BotSuperClass

log = logging.getLogger('updatebot.ordered')

class Bot(BotSuperClass):
    """
    Implement errata driven create/update interface.
    """

    _create = BotSuperClass.create
    _update = BotSuperClass.update

    def __init__(self, cfg, errataSource):
        BotSuperClass.__init__(self, cfg)
        self._errata = errata.ErrataFilter(self._pkgSource, errataSource)

    def create(self, *args, **kwargs):
        """
        Handle initial import case.
        """

        self._pkgSource.load()
        toCreate = self._errata.getInitialPackages()
        return self._create(*args, toCreate=toCreate, **kwargs)

    def update(self, *args, **kwargs):
        """
        Handle update case.
        """

        # Get current timestamp
        # FIXME: Figure out where to store current errata level
        raise NotImplementedError

        current = 0

        self._pkgSource.load()

        for updateId, updates in self._errata.iterByIssueDate(start=current):
            detail = self._errata.getUpdateDetail(updateId)
            log.info('attempting to apply %s' % detail)

            # Update package set.
            self._update(updatePkgs=updates)

            # Store current updateId.
            # FIXME: figure out where/how to store the current updateId

