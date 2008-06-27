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
Module to wrap around conary api. Maybe this could be replaced by rbuild at
some point.
"""

import os
import time
import logging
import tempfile

from conary.build import use
from conary import conaryclient, conarycfg, trove, checkin

from updatebot import util
from updatebot.errors import TooManyFlavorsFoundError
from updatebot.errors import NoManifestFoundError
from updatebot.errors import PromoteFailedError
from updatebot.errors import PromoteMismatchError

log = logging.getLogger('updatebot.conaryhelper')

class ConaryHelper(object):
    """
    Wrapper object for conary api.
    """

    def __init__(self, cfg):
        self._ccfg = conarycfg.ConaryConfiguration(readConfigFiles=False)
        self._ccfg.read(util.join(cfg.configPath, 'conaryrc'))
        # Have to initialize flavors to commit to the repository.
        self._ccfg.initializeFlavors()

        self._client = conaryclient.ConaryClient(self._ccfg)
        self._repos = self._client.getRepos()

    def getConaryConfig(self):
        """
        Get a conary config instance.
        @return conary configuration object
        """

        return self._ccfg

    def getSourceTroves(self, group):
        """
        Find all of the source troves included in group. If group is None use
        the top level group config option.
        @param group: group to query
        @type group: None or troveTuple (name, versionStr, flavorStr)
        @return set of source trove specs
        """

        # E1101 - Instance of 'ConaryConfiguration' has no 'buildLabel' member
        # pylint: disable-msg=E1101

        trvlst = self._repos.findTrove(self._ccfg.buildLabel, group)

        latest = self._findLatest(trvlst)

        # Magic number should probably be a config option.
        # 2 here is the number of flavors expected.
        if len(latest) != 2:
            raise TooManyFlavorsFoundError(why=latest)

        srcTrvs = set()
        for trv in latest:
            log.info('querying %s for source troves' % (trv, ))
            srcTrvs.update(self._getSourceTroves(trv))

        return srcTrvs

    @staticmethod
    def _findLatest(trvlst):
        """
        Given a list of trove specs, find the most recent versions.
        @param trvlst: list of trove specs
        @type trvlst: [(name, versionObj, flavorObj), ...]
        @return [(name, versionObj, flavorObj), ...]
        """

        latest = []

        trvlst.sort()
        trvlst.reverse()
        while len(trvlst) > 0:
            trv = trvlst.pop(0)
            if len(latest) == 0 or latest[-1][1] == trv[1]:
                latest.append(trv)
            else:
                break

        return latest

    def _getSourceTroves(self, troveSpec):
        """
        Iterate over the contents of a trv to find all of source troves
        refrenced by that trove.
        @param troveSpec: trove to walk.
        @type troveSpec: (name, versionObj, flavorObj)
        @return set([(trvSpec, trvSpec, ...])
        """

        # W0212 - Access to a protected member _TROVEINFO_TAG_SOURCENAME of a
        #         client class
        # pylint: disable-msg=W0212

        name, version, flavor = troveSpec
        cl = [ (name, (None, None), (version, flavor), True) ]
        cs = self._client.createChangeSet(cl, withFiles=False,
                                          withFileContents=False,
                                          recurse=False)

        topTrove = self._getTrove(cs, name, version, flavor)

        # Iterate over both strong and weak refs because msw said it was a
        # good idea.
        srcTrvs = set()
        sources = self._repos.getTroveInfo(trove._TROVEINFO_TAG_SOURCENAME,
                    list(topTrove.iterTroveList(weakRefs=True,
                                                strongRefs=True)))
        for i, (_, v, _) in enumerate(topTrove.iterTroveList(weakRefs=True,
                                                            strongRefs=True)):
            srcTrvs.add((sources[i](), v.getSourceVersion(), None))

        return srcTrvs

    @staticmethod
    def _getTrove(cs, name, version, flavor):
        """
        Get a trove object for a given name, version, flavor from a changeset.
        @param cs: conary changeset object
        @type cs: changeset
        @param name: name of a trove
        @type name: string
        @param version: conary version object
        @type version: conary.versions.Version
        @param flavor: conary flavor object
        @type flavor: conary.deps.Flavor
        @return conary.trove.Trove object
        """

        #log.debug('getting trove for (%s, %s, %s)' % (name, version, flavor))
        troveCs = cs.getNewTroveVersion(name, version, flavor)
        trv = trove.Trove(troveCs, skipIntegrityChecks=True)
        return trv

    def getManifest(self, pkgname):
        """
        Get the contents of the manifest file from the source component for a
        given package.
        @param pkgname: name of the package to retrieve
        @type pkgname: string
        @return manifest for pkgname
        """

        log.info('retrieving manifest for %s' % pkgname)
        recipeDir = self._checkout(pkgname)
        manifestFileName = util.join(recipeDir, 'manifest')

        if not os.path.exists(manifestFileName):
            raise NoManifestFoundError(pkgname=pkgname, dir=recipeDir)

        manifest = [ x.strip() for x in open(manifestFileName).readlines() ]
        util.rmtree(recipeDir)
        return manifest

    def setManifest(self, pkgname, manifest, commitMessage=''):
        """
        Create/Update a manifest file.
        @param pkgname: name of the package
        @type pkgname: string
        @param manifest: list of files to go in the manifest file
        @type manifest: list(string, string, ...)
        @param commitMessage: optional argument for setting the commit message
                              to use when committing to the repository.
        @type commitMessage: string
        """

        log.info('setting manifest for %s' % pkgname)

        # Figure out if we should create or update.
        if not self._getVersionsByName('%s:source' % pkgname):
            recipeDir = self._newpkg(pkgname)
        else:
            recipeDir = self._checkout(pkgname)

        # Update manifest file.
        manifestFileName = util.join(recipeDir, 'manifest')
        manifestfh = open(manifestFileName, 'w')
        manifestfh.write('\n'.join(manifest))
        manifestfh.write('\n')
        manifestfh.close()

        # Setup flavor objects
        use.setBuildFlagsFromFlavor(pkgname, self._ccfg.buildFlavor,
                                    error=False)

        # Commit to repository.
        self._commit(recipeDir, commitMessage)
        util.rmtree(recipeDir)

        # Get new version of the source trove.
        versions = self._getVersionsByName('%s:source' % pkgname)
        assert len(versions) == 1
        return versions[0]

    def _checkout(self, pkgname):
        """
        Checkout a source component from the repository.
        @param pkgname: name of the package to checkout
        @type pkgname: string
        @return checkout directory
        """

        log.info('checking out %s' % pkgname)

        recipeDir = tempfile.mkdtemp(prefix='conaryhelper-')
        checkin.checkout(self._repos, self._ccfg, recipeDir, [pkgname, ])

        return recipeDir

    def _commit(self, pkgDir, commitMessage):
        """
        Commit a source trove to the repository.
        @param pkgDir: directory returned by checkout
        @type pkgDir: string
        @param commitMessage: commit message to use.
        @type commitMessage: string
        """

        log.info('committing %s' % os.path.basename(pkgDir))

        cwd = os.getcwd()
        try:
            os.chdir(pkgDir)
            checkin.commit(self._repos, self._ccfg, commitMessage)
        finally:
            os.chdir(cwd)

    def _newpkg(self, pkgname):
        """
        Create a new source component.
        @param pkgname: name of the package to create.
        @type pkgname: string
        @return checkout directory
        """

        log.info('creating new package %s' % pkgname)

        recipeDir = tempfile.mkdtemp(prefix='conaryhelper-')

        cwd = os.getcwd()
        try:
            os.chdir(recipeDir)
            checkin.newTrove(self._repos, self._ccfg, pkgname)
        finally:
            os.chdir(cwd)

        return util.join(recipeDir, pkgname)

    def _getVersionsByName(self, pkgname):
        """
        Figure out if a trove exists in the repository.
        @param pkgname: name of the package to look for.
        @type pkgname: string
        """

        # E1101 - Instance of 'ConaryConfiguration' has no 'buildLabel' member
        # pylint: disable-msg=E1101

        label = self._ccfg.buildLabel

        trvMap = self._repos.getTroveLeavesByLabel({pkgname: {label: None }})
        verMap = trvMap.get(pkgname, {})
        versions = verMap.keys()
        return versions

    def promote(self, trvLst, expected, sourceLabels, targetLabel):
        """
        Promote a group and its contents to a target label.
        @param trvLst: list of troves to publish
        @type trvLst: [(name, version, flavor), ... ]
        @param expected: list of troves that are expected to be published.
        @type expected: [(name, version, flavor), ...]
        @param sourceLabels: list of labels that should be flattened onto the
                             targetLabel.
        @type sourceLabels: [labelObject, ... ]
        @param targetLabel: table to publish to
        @type targetLabel: conary Label object
        """

        start = time.time()
        log.info('starting promote')
        log.info('creating changeset')

        # Get the label that the group is on.
        fromLabel = trvLst[0][1].trailingLabel()

        # Build the label map.
        labelMap = {fromLabel: targetLabel}
        for label in sourceLabels:
            labelMap[label] = targetLabel

        success, cs = self._client.createSiblingCloneChangeSet(
                            labelMap,
                            trvLst,
                            cloneSources=True)

        log.info('changeset created in %s' % (time.time() - start, ))

        if not success:
            raise PromoteFailedError(what=trvLst)

        packageList = [ x.getNewNameVersionFlavor()
                        for x in cs.iterNewTroveList() ]

        oldPkgs = set([ (x[0], x[2]) for x in expected if not x[0].endswith(':source') ])
        newPkgs = set([ (x[0], x[2]) for x in packageList if not x[0].endswith(':source') ])

        # Make sure that all packages being promoted are in the set of packages
        # that we think should be available to promote. Note that all packages
        # in expected will not be promoted because not all packages are
        # included in the groups.
        difference = newPkgs.difference(oldPkgs)
        grpTrvs = set([ (x[0], x[2]) for x in trvLst if not x[0].endswith(':source') ])
        if difference != grpTrvs:
            raise PromoteMismatchError(expected=oldPkgs, actual=newPkgs)

        log.info('committing changeset')

        self._repos.commitChangeSet(cs)

        log.info('changeset committed')
        log.info('promote complete, elapsed time %s' % (time.time() - start, ))

        return packageList
