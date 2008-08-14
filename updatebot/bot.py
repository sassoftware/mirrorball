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

import time
import logging

import repomd

from updatebot import build
from updatebot import update
from updatebot import advise
from updatebot import pkgsource
from updatebot import patchsource

log = logging.getLogger('updatebot.bot')

class Bot(object):
    """
    Top level object for driving update process.
    """

    def __init__(self, cfg):
        self._cfg = cfg

        self._pkgSourcePopulated = False
        self._patchSourcePopulated = False

        self._clients = {}
        self._pkgSource = pkgsource.PackageSource(self._cfg)
        self._patchSource = patchsource.PatchSource(self._cfg)
        self._updater = update.Updater(self._cfg, self._pkgSource)
        self._advisor = advise.Advisor(self._cfg, self._pkgSource,
                                       self._patchSource)
        self._builder = build.Builder(self._cfg)

    def _populateRpmSource(self):
        """
        Populate the rpm source data structures.
        """

        if self._pkgSourcePopulated:
            return

        for repo in self._cfg.repositoryPaths:
            log.info('loading repository data %s/%s'
                     % (self._cfg.repositoryUrl, repo))
            client = repomd.Client(self._cfg.repositoryUrl + '/' + repo)
            self._pkgSource.loadFromClient(client, repo)
            self._clients[repo] = client
        self._pkgSource.finalize()

        self._pkgSourcePopulated = True

    def _populatePatchSource(self):
        """
        Populate the patch source data structures.
        """

        if self._patchSourcePopulated:
            return

        for path, client in self._clients.iteritems():
            log.info('loading patch information %s/%s'
                     % (self._cfg.repositoryUrl, path))
            self._patchSource.loadFromClient(client, path)

        self._patchSourcePopulated = True

    @staticmethod
    def _flattenSetDict(setDict):
        """
        Convert a dictionary with values of sets to a list.
        @param setList: dictionary of sets
        @type setList: [set(), set(), ...]
        @return list of items that were in the sets
        """

        lst = []
        for trvSet in setDict.itervalues():
            lst.extend(list(trvSet))
        return lst

    def create(self):
        """
        Do initial imports.
        """

        start = time.time()
        log.info('starting import')

        # Populate rpm source object from yum metadata.
        self._populateRpmSource()

        #import epdb; epdb.st()

        # Import sources into repository.
        toBuild, fail = self._updater.create(self._cfg.package)

#        import epdb; epdb.st()

        # Build all newly imported packages.
        #trvMap, failed = self._builder.buildmany(toBuild)
        #trvMap = self._builder.build(toBuild)
        trvs = self._builder._formatInput(toBuild)
        jobs = {}
        for trv in trvs:
            key = 'other'
            if len(trv) == 4:
                key = trv[3]

            if key not in jobs:
                jobs[key] = []

            jobs[key].append(trv)

        ids = {}
        for job in jobs:
            if job == 'other':
                continue

            ids[job] = self._builder._startJob(jobs[job])

        for job in ids:
            self._builder._monitorJob(ids[job])

        log.info('completed jobs %s' % (' '.join(ids.values()), ))

        import epdb; epdb.st()

        for trv in self._flattenSetDict(trvMap):
            log.info('built: %s' % trv)

        import epdb; epdb.st()

        log.info('import completed successfully')
        log.info('imported %s source packages' % (len(toBuild), ))
        log.info('elapsed time %s' % (time.time() - start, ))

        return trvMap

    def update(self):
        """
        Update the conary repository from the yum repositories.
        """

        start = time.time()
        log.info('starting update')

        # Populate rpm source object from yum metadata.
        self._populateRpmSource()

        # Get troves to update and send advisories.
        toAdvise, toUpdate = self._updater.getUpdates()

        if len(toAdvise) == 0:
            log.info('no updates available')
            return

        # Populate patch source not that we know that there are updates
        # available.
        self._populatePatchSource()

        # Check to see if advisories exist for all required packages.
        self._advisor.check(toAdvise)

        # Update source
        for nvf, srcPkg in toUpdate:
            toAdvise.remove((nvf, srcPkg))
            newVersion = self._updater.update(nvf, srcPkg)
            toAdvise.append(((nvf[0], newVersion, nvf[2]), srcPkg))

        # Make sure to build everything in the toAdvise list, there may be
        # sources that have been updated, but not built.
        buildTroves = set([ x[0] for x in toAdvise ])
        trvMap = self._builder.build(buildTroves)

        # Build group.
        grpTrvs = set()
        for flavor in self._cfg.groupFlavors:
            grpTrvs.add((self._cfg.topSourceGroup[0],
                         self._cfg.topSourceGroup[1],
                         flavor))
        grpTrvMap = self._builder.build(grpTrvs)

        # Promote group.
        # We expect that everything that was built will be published.
        expected = self._flattenSetDict(trvMap)
        toPublish = self._flattenSetDict(grpTrvMap)
        newTroves = self._updater.publish(toPublish, expected,
                                          self._cfg.targetLabel)

        import epdb; epdb.st()

        # Send advisories.
        self._advisor.send(toAdvise, newTroves)

        log.info('update completed successfully')
        log.info('updated %s packages and sent %s advisories'
                 % (len(toUpdate), len(toAdvise)))
        log.info('elapsed time %s' % (time.time() - start, ))
