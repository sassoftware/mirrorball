#
# Copyright (c) 2008 rPath, Inc.
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
Module for driving the update process.
"""

import logging

import repomd
from rpmvercmp import rpmvercmp
from rpmimport import rpmsource

from updatebot import util
from updatebot import build
from updatebot import update
from updatebot import advise
from updatebot import patchsource
from updatebot.errors import *

log = logging.getLogger('updatebot.bot')

class Bot(object):
    """
    Top level object for driving update process.
    """

    def __init__(self, cfg):
        self._cfg = cfg

        self._clients = {}
        self._rpmSource = rpmsource.RpmSource()
        self._patchSource = patchsource.PatchSource()
        self._updater = update.Updater(self._cfg, self._rpmSource)
        self._advisor = advise.Advisor(self._cfg, self._rpmSource,
                                       self._patchSource)
        self._builder = build.Builder(self._cfg)

    def _populateRpmSource(self):
        """
        Populate the rpm source data structures.
        """

        for repo in self._cfg.repositoryPaths:
            log.info('loading %s/%s repository data'
                     % (self._cfg.repositoryUrl, repo))
            client = repomd.Client(self._cfg.repositoryUrl + '/' + repo)
            self._rpmSource.loadFromClient(client, repo)
            self._clients[repo] = client
        self._rpmSource.finalize()

    def _populatePatchSource(self):
        """
        Populate the patch source data structures.
        """

        for path, client in self._clients.iteritems():
            log.info('loading %s/%s patch information'
                     % (self._cfg.repositoryUrl, path))
            self._patchSource.loadFromClient(client, path)

    def run(self):
        """
        Update the conary repository from the yum repositories.
        """

        log.info('starting update')

        # Populate rpm source object from yum metadata.
        self._populateRpmSource()

        # Get troves to update and send advisories.
        toAdvise, toUpdate = self._updater.getUpdates()

        # Don't populate the patch source until we knoe that there are
        # updatas.
        self._populatePatchSource()

        # Check to see if advisories exist for all required packages.
        self._advisor.check(toAdvise)

        # Update sources.
        for nvf, srcPkg in toUpdate:
            self._updater.update(nvf, srcPkg)

        # Make sure to build everything in the toAdvise list, there may be
        # sources that have been updated, but not built.
        buildTroves = [ x[0] for x in toAdvise ]
        trvMap = self._builder.build(buildTroves)

        # Build group.
        grpTrvMap = self._builder.build(self._cfg.topGroup)

        # Promote group.
        # FIXME: should be able to get the new versions of packages from
        #        promote.
        helper = self._updater.getConaryHelper()
        newTroves = helper.promote(grpTrvMap.values(), self._cfg.targetLabel)

        # FIXME: build a trvMap from source tove nvf to new binary trove nvf

        # Send advisories.
        self._advisor.send(trvMap, toAdvise)

        log.info('update completed successfully')
        log.info('updated %s packages and sent %s advisories'
                 % (len(toUpdate), len(toAdvise)))
