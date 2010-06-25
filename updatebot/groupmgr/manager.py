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
Module for managing conary groups.
"""

import logging

from conary import versions

from updatebot.build import Builder

from updatebot.errors import NotCommittingOutOfDateSourceError

from updatebot.groupmgr.group import Group
from updatebot.groupmgr.group import require_write
from updatebot.groupmgr.helper import GroupHelper
from updatebot.groupmgr.sanity import GroupSanityChecker

log = logging.getLogger('updatebot.groupmgr')

class GroupManager(object):
    """
    Class for managing groups.
    @param cfg: updatebot configuration object
    @type cfg: updatebot.config.UpdateBotConfig
    @param ui: updatebot user interface object
    @type ui: updatebot.cmdline.ui.UserInterface
    @param parentGroup: optional argument, if set to True will setup manager to
                        interact with the parent platform group contents. This
                        is automatically set to readonly to avoid writing
                        anything to the parent platform.
    @type parentGroup: boolean
    @param targetGroup: optional argument, if set to True will setup manager to
                        interact with the target "production" branch for the
                        configured platform. This manager instance will
                        automatically be set to readonly to avoid modifying the
                        target label.
    @type targetGroup: boolean
    @param useMap: optional argument, A dictionary of package names mapped to a
                   list of use flags for the given package name. This is used to
                   determine use flags for packages that are added to group
                   contents models. If not specified all x86 packages will be
                   added to the x86 group and all x86_64 packages will be added
                   to the x86_64 group.
    @type useMap: dict
    """

    _helperClass = GroupHelper
    _sanityCheckerClass = GroupSanityChecker

    def __init__(self, cfg, ui, parentGroup=False, targetGroup=False,
        useMap=None):

        self._cfg = cfg
        self._ui = ui

        if useMap is None:
            self._useMap = {}
        else:
            self._useMap = useMap

        self._helper = self._helperClass(self._cfg)
        self._builder = Builder(self._cfg, self._ui,
            rmakeCfgFn='rmakerc-groups')
        self._sanity = self._sanityCheckerClass(self._cfg, self._helper)

        assert not (parentGroup and targetGroup)

        srcName = self._cfg.topSourceGroup[0]
        srcLabel = self._cfg.topSourceGroup[1]
        labels = None

        if targetGroup:
            srcLabel = self._cfg.targetLabel
        elif parentGroup:
            srcName = self._cfg.topParentSourceGroup[0]
            srcLabel = self._cfg.topParentSourceGroup[1]
            labels = self._cfg.platformSearchPath

        if not srcName.endswith(':source'):
            srcName = '%s:source' % srcName

        self._sourceName = srcName
        self._sourceLabel = srcLabel
        self._searchLabels = labels

        self._pkgGroupName = self._cfg.packageGroupName

        self._readOnly = False
        if targetGroup or parentGroup:
            self._readOnly = True

        self._groupCache = {}
        self._latest = None

    def setReadOnly(self):
        """
        Mark the group manager as read only. You will not be able to modify or
        build any groups requested through this manager instance.
        """

        self._readOnly = True

    @property
    def latest(self):
        if self._latest is None:
            self._latest = self.getGroup()
        return self._latest

    def _findVersion(self, version=None, allVersions=False):
        """
        Find the conary version(s) that match the specified version.
        @param version: The conary source version to load or a string
                        representation of the version that will be looked up in
                        the repository. The latest source version matching the
                        specified version will be used. If no version is
                        specified, the latest version will be retreived.
        @type version: conary.versions.VersionFromString, str, or None
        @param allVersions: By default this method only finds the latest
                            versions. If you would like to find all versions
                            that match the specified version set this option
                            to True.
        @type allVersions: boolean
        @return conary version(s) found
        @rtype conary.versions.VersionFromString
        @rtype list(conary.versions.VersionFromString)
        """

        # Make sure version is of an acceptable type.
        assert (isinstance(version, (str, versions.VersionSequence)) or
               version is None)

        # Find the latest version so that we can check if the version we are
        # retreiving from the repository is the latest.
        trvs = self._helper.findTrove((self._sourceName, version, None),
                                      labels=self._searchLabels,
                                      getLeaves=not allVersions)

        if allVersions:
            return [ x[1] for x in trvs ]
        elif len(trvs):
            return trvs[0][1]
        else:
            return None

    def _persistGroup(self, group, conaryVersion=None):
        """
        Serialize the contents of a group model to disk.
        @param conaryVersion: The version of the group source to update.
        @type conaryVersion: conary.versions.VersionFromString
        """

        if not conaryVersion:
            conaryVersion = group.conaryVersion

        # set version
        self._helper.setVersion(self._sourceName, group.version,
            version=conaryVersion)

        # set errata state
        self._helper.setErrataState(self._sourceName, group.errataState,
            version=conaryVersion)

        # write out the model data
        self._helper.setModel(self._sourceName, group, version=conaryVersion)

    def getGroup(self, version=None):
        """
        Retrieve a group model from the repository.
        @param version: The conary source version to load or a string
                        representation of the version that will be looked up in
                        the repository. The latest source version matching the
                        specified version will be used. If no version is
                        specified, the latest version will be retreived.
        @type version: conary.versions.VersionFromString, str, or None
        @return group model object
        @rtype updatebot.groupmgr.group.Group
        """

        # Make sure version is of an acceptable type.
        assert (isinstance(version, (str, versions.VersionSequence)) or
               version is None)

        # Find the latest version so that we can check if the version we are
        # retreiving from the repository is the latest.
        latest = self._findVersion()

        # Find the conary version object if we don't have one yet.
        if version is None:
            conaryVersion = latest
        elif isinstance(version, str):
            conaryVersion = self._findVersion(version=version)
            # If the user requested a version that doesn't exist return None.
            if conaryVersion is None:
                return None
        else:
            conaryVersion = version

        # Make sure this is a source version.
        assert conaryVersion is None or conaryVersion.isSourceVersion()

        # Check the cache for this version first.
        if conaryVersion in self._groupCache:
            return self._groupCache[conaryVersion]

        # Get model information from the source.
        groups = self._helper.getModel(self._sourceName, version=conaryVersion)
        errataState = self._helper.getErrataState(self._sourceName,
            version=conaryVersion)
        upstreamVersion = self._helper.getVersion(self._sourceName,
            version=conaryVersion)

        # Instantiate a group instance.
        group = Group(self._cfg, self._useMap, self._sanity, self,
            self._pkgGroupName, groups, errataState, upstreamVersion,
            conaryVersion)

        # If this was the latest version, store it as "latest"
        if conaryVersion == latest:
            self._latest = group

        # Cache reference to group.
        self._groupCache[conaryVersion] = group

        return group

    @require_write
    def setGroup(self, group, copyToLatest=False):
        """
        Freeze group model and commit state to the repository. Note that this
        puts the group model object into read only mode.
        @param group: group object to commit
        @type group: updatebot.groupmgr.group.Group
        @param copyToLatest: Optional parameter to enable committing a model
                             that was not gerenated from the latest version.
        @type copyToLatest: boolean
        @return committed group model object
        @rtype updatebot.groupmgr.group.Group
        """

        # Make sure model hasn't already been committed.
        assert not group.committed

        # Don't attempt to commit out of date sources unless requested to do so.
        if (group.conaryVersion != self.latest.conaryVersion and
            not copyToLatest):

            log.error('refusing to commit out of date source')
            raise NotCommittingOutOfDateSourceError

        # Copy forward data when we are fixing up old group versions so that
        # this is the latest source.
        if copyToLatest:
            log.info('committing %s model as latest' % group.conaryVersion)
            log.info('version: %s' % group.version)
            log.info('errataState: %s' % group.errataState)

            conaryVersion = self.latest.conaryVersion

        # Default to modifying the source verison of the group model.
        else:
            conaryVersion = group.conaryVersion

        # Finalizing the group performs any sanity checking and marks it as
        # readonly.
        group.finalize()

        # Serialize the group model.
        self._persistGroup(group, conaryVersion=conaryVersion)

        # commit to the repository
        newVersion = self._helper.commit(self._sourceName,
            version=conaryVersion,
            commitMessage=self._cfg.commitMessage)

        # Remove the cached version of the already committed group.
        self._groupCache.pop(group.conaryVersion)

        # Mark group as committed.
        group.setCommitted()

        # Get the model for the source version that we just committed.
        return self.getGroup(version=newVersion)

    @require_write
    def buildGroup(self, group, multiBuild=False):
        """
        Build the binary version of a given group.
        @param group: group model to build.
        @type group: updatebot.groupmgr.group.Group
        @param multiBuild: Optional parameter, defaults to False, control if
                           builder can build multiple packages at once.
        @type mutliBuild: boolean
        @return mapping of built troves, if multiBuild return results object.
        @rtype dict(sourceTrv=[binTrv, ..]) or updatebot.build.jobs.Status
        """

        # Make sure this group has been committed to the repository before
        # attempting to build it.
        assert group.committed

        # Make sure this group is not marked as dirty. This means that things
        # have been changed about the group since it was committed.
        assert not group.dirty

        # Find all of the use flags used in the group model.
        use = set()
        for model in group:
            for pkg in model:
                if pkg.use:
                    use.add(pkg.use)
                else:
                    use.update(set(['x86', 'x86_64']))

        # Create a build job and build groups using cvc.
        job = ((self._sourceName, group.conaryVersion, None), )

        if not multiBuild:
            results = self._builder.cvc.cook(job, flavorFilter=use)
        else:
            results = self._builder.cvc.build(job[0], flavorFilter=use)

        return results

    def getSourceVersions(self):
        """
        Retrieve a list of all available group source versions.
        @return list of conary versions
        @rtype list(conary.versions.VersionFromString, ...)
        """

        return self._findVersion(allVersions=True)

    def hasBinaryVersion(self, sourceVersion=None):
        """
        Check if there is a binary for a given source version.
        @param sourceVersion: If specified check for a binary version for the
                              given source verison.
        @type sourceVersion: conary.versions.VersionFromString
        @return True if the binary version exists, otherwise False.
        @rtype boolean
        """

        # Default to the latest source version if none is specified.
        if sourceVersion is None:
            sourceVersion = self.latest.conaryVersion

        # Resolve version to a conary version.
        sourceVersion = self._findVersion(version=sourceVersion)

        # If the version doesn't exist in the repository return False.
        if sourceVersion is None:
            return False

        # Make sure it is really a source version.
        assert sourceVersion.isSourceVersion()

        # Get the list of binaries for this source from the repository.
        # FIXME: This should not call into the conary client itself, instead
        #        there should be a call in the conary helper.
        trvs = self._helper._repos.getTrovesBySource(self._sourceName, 
            sourceVersion)

        return bool(len(trvs))
