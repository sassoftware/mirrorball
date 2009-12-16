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
An abstraction layer around cvc cook.
"""

import copy
import logging

log = logging.getLogger('updatebot.build.cvc')

from conary import conarycfg
from conary.build import cook

from updatebot.lib import conarycallbacks
from updatebot.errors import LocalCookFailedError

class Cvc(object):
    """
    This is initially intended to only implement interfaces for cooking groups
    locally, but could and should be extended to building other kinds of
    troves. This would be useful for building packages that do not depend on
    environment, such as factories and superclasses. Additionally implementing
    a general abstraction around cvc for all cvc operations could be very handy.
    @param cfg: updatebot config object
    @type cfg: updatebot.config.UpdateBotConfiguration
    @param ccfg: conary configuration object
    @type ccfg: conary.conarycfg.ConaryConfiguration
    @param client: conary client object
    @type client: conary.conaryclient.ConaryClient
    @param inputFormatter: method to format trove lists into approriate tuples.
    @type inputFormatter: method
    """

    def __init__(self, cfg, ccfg, inputFormatter):
        self._cfg = cfg
        self._ccfg = copy.deepcopy(ccfg)
        self._formatInput = inputFormatter

        # Restet dbPath to the default value for local cooking.
        self._ccfg.dbPath = conarycfg.ConaryContext.dbPath

    def cook(self, troveSpecs):
        """
        Cook a set of trove specs, currently limited to groups.
        @params troveSpecs: list of name, version, and flavor tuples.
        @type troveSpecs: [(name, version, flavor), ... ]
        """

        # TODO: Look at conary.build.cook.cookCommand for how to setup
        #       environment when building anything other than groups.

        troveSpecs = self._formatInput(troveSpecs)

        # make sure all troves are groups
        assert not [ x for x in troveSpecs if not x[0].startswith('group-') ]

        # make sure that all groups are the same name and version.
        assert len(set([ (x[0], x[1]) for x in troveSpecs])) == 1

        # pulled from conary.cvc
        groupCookOptions = cook.GroupCookOptions(
            alwaysBumpCount = True,
            errorOnFlavorChange = True,
            shortenFlavors = self._ccfg.shortenGroupFlavors
        )

        # extract flavor set
        flavors = set([ x[2] for x in troveSpecs ])
        item = (troveSpecs[0][0], troveSpecs[0][1], flavors)

        built = cook.cookItem(
            self._client.repos,
            self._ccfg,
            item,
            ignoreDeps=True,
            logBuild=True,
            callback=conarycallbacks.UpdateBotCookCallback(),
            groupOptions=groupCookOptions,
        )

        if built is None:
            raise LocalCookFailedError(troveSpecs=troveSpecs)

        components, csFile = built

        if not components:
            raise LocalCookFailedError(troveSpecs=troveSpecs)

        if csFile is None:
            log.info('changeset committed to repository')

        res = { (troveSpecs[0][0], troveSpecs[0][1], None): set(components) }
        return res
