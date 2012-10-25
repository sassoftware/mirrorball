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
Module for sanity checking group contents model.
"""

import logging
import itertools

from conary import versions
from conary.deps import deps

from updatebot.errors import OldVersionsFoundError
from updatebot.errors import GroupValidationFailedError
from updatebot.errors import NameVersionConflictsFoundError
from updatebot.errors import ExpectedRemovalValidationFailedError

log = logging.getLogger('updatebot.groupmgr')

class GroupSanityChecker(object):
    """
    Class for checking group model sanity.
    """

    def __init__(self, cfg, helper):
        self._cfg = cfg
        self._helper = helper

    def check(self, groups, errataState):
        """
        Validate the contents of the package group to ensure sanity:
            1. Check for packages that have the same source name, but
               different versions.
            2. Check that the version in the group is the latest source/build
               of that version.
            3. Check that package removals specified in the config file have
               occured.
        """

        errors = []
        for name, group in groups.iteritems():
            log.info('checking consistency of %s' % name)
            try:
                log.info('checking name version conflict')
                self._checkNameVersionConflict(group)
            except NameVersionConflictsFoundError, e:
                errors.append((group, e))

            # FIXME: This is a hack, there should be a better way of controlling
            #        what policy runs for a particular group.
            if 'standard' not in name:
                try:
                    log.info('checking latest versions')
                    self._checkLatestVersion(group)
                except OldVersionsFoundError, e:
                    errors.append((group, e))

            try:
                log.info('checking removals')
                self._checkRemovals(group, errataState)
            except ExpectedRemovalValidationFailedError, e:
                errors.append((group, e))

        if errors:
            raise GroupValidationFailedError(errors=errors)

    def _checkNameVersionConflict(self, group):
        """
        Check for packages taht have the same source name, but different
        versions.
        """

        # get names and versions
        troves = set()
        labels = set()
        for pkgKey, pkgData in group.iteritems():
            name = str(pkgData.name)

            version = None
            if pkgData.version:
                versionObj = versions.ThawVersion(pkgData.version)
                labels.add(versionObj.branch().label())
                version = str(versionObj.asString())

            flavor = None
            # FIXME: At some point we might want to add proper flavor handling,
            #        note that group flavor handling is different than what
            #        findTroves normally does.
            #if pkgData.flavor:
            #    flavor = deps.ThawFlavor(str(pkgData.flavor))

            troves.add((name, version, flavor))

        # Get flavors and such.
        foundTroves = set([ x for x in
            itertools.chain(*self._helper.findTroves(troves,
                                                labels=labels).itervalues()) ])

        # get sources for each name version pair
        sources = self._helper.getSourceVersions(foundTroves)

        seen = {}
        for (n, v, f), pkgSet in sources.iteritems():
            binVer = list(pkgSet)[0][1]
            seen.setdefault(n, set()).add(binVer)

        binPkgs = {}
        conflicts = {}
        for name, vers in seen.iteritems():
            if len(vers) > 1:
                log.error('found multiple versions of %s' % name)
                for binVer in vers:
                    srcVer = binVer.getSourceVersion()
                    nvf = (name, srcVer, None)
                    conflicts.setdefault(name, []).append(srcVer)
                    binPkgs[nvf] = sources[nvf]

        if conflicts:
            raise NameVersionConflictsFoundError(groupName=group.groupName,
                                                 conflicts=conflicts,
                                                 binPkgs=binPkgs)

    def _checkLatestVersion(self, group):
        """
        Check to make sure each specific conary version is the latest source
        and build count of the upstream version.
        """

        # get names and versions
        troves = set()
        labels = set()
        for pkgKey, pkgData in group.iteritems():
            name = str(pkgData.name)

            version = None
            if pkgData.version:
                version = versions.ThawVersion(pkgData.version)
                labels.add(version.branch().label())
                # get upstream version
                revision = version.trailingRevision()
                upstreamVersion = revision.getVersion()

                # FIXME: This should probably be a fully formed version
                #        as above.
                version = version.branch().label().asString() + '/' + upstreamVersion

            flavor = None
            # FIXME: At some point we might want to add proper flavor handling,
            #        note that group flavor handling is different than what
            #        findTroves normally does.
            #if pkgData.flavor:
            #    flavor = deps.ThawFlavor(str(pkgData.flavor))

            troves.add((name, version, flavor))

        # Get flavors and such.
        foundTroves = dict([ (x[0], y) for x, y in
            self._helper.findTroves(troves, labels=labels).iteritems() ])

        pkgs = {}
        for pkgKey, pkgData in group.iteritems():
            name = str(pkgData.name)
            version = None
            if pkgData.version:
                version = versions.ThawVersion(pkgData.version)
            flavor = None
            if pkgData.flavor:
                flavor = deps.ThawFlavor(str(pkgData.flavor))

            pkgs.setdefault(name, []).append((name, version, flavor))

        assert len(pkgs) == len(foundTroves)

        # Get all old versions so that we can make sure any version conflicts
        # were introduced by old version handling.
        oldVersions = set()
        if self._cfg.platformSearchPath:
            qlabels = set(self._cfg.platformSearchPath) | labels
        else:
            qlabels = labels
        for nvfLst in self._cfg.useOldVersion.itervalues():
            for nvf in nvfLst:
                srcMap = self._helper.getSourceVersionMapFromBinaryVersion(nvf,
                        labels=qlabels, latest=False)
                oldVersions |= set(itertools.chain(*srcMap.itervalues()))

        errors = {}
        for name, found in foundTroves.iteritems():
            assert name in pkgs
            # Make sure to dedup packages from the model since a name/version
            # pair can occure more than once.
            current = sorted(set(pkgs[name]))

            # FIXME: HACK to filter found for the versions in current.
            # Do to some issues early on with building pkgs with missing
            # flavors findTroves is returning some extra cruft.
            current_versions = [ currentnvf[1] for currentnvf in current ]
            found = [ nvf for nvf in found if nvf[1] in current_versions ]
            
            if len(current) > len(found):
                log.warn('found more packages in the model than in the '
                    'repository, assuming that multiversion policy will '
                    'catch this.')
                continue

            assert len(current) == 1 or len(found) == len(current)

            foundError = False
            for i, (n, v, f) in enumerate(found):
                if len(current) == 1:
                    i = 0
                cn, cv, cf = current[i]
                assert n == cn

                if v != cv:
                    if (n, v, f) in oldVersions:
                        log.info('found %s=%s[%s] in oldVersions exceptions'
                                 % (n, v, f))
                        continue

                    # This is probably a flavor that we don't care about
                    # anymore.
                    if cv > v and cv in [ x[1] for x in found ]:
                        log.warn('missing flavors found of %s that are not all '
                                 'included in the group, assuming this '
                                 'intentional.' % cn)
                        continue

                    foundError = True

            if foundError:
                log.error('found old version for %s' % name)
                errors[name] = (current, found)

        if errors:
            raise OldVersionsFoundError(pkgNames=errors.keys(), errors=errors)

    def _checkRemovals(self, group, updateId):
        """
        Check to make sure that all configured package removals have happened.
        """

        # get package removals from the config object.
        removePackages = self._cfg.updateRemovesPackages.get(updateId, [])
        removeObsoleted = self._cfg.removeObsoleted.get(updateId, [])
        removeSource = [ x[0] for x in
                         self._cfg.removeSource.get(updateId, []) ]

        # get names and versions
        troves = set()
        labels = set()
        for pkgKey, pkgData in group.iteritems():
            name = str(pkgData.name)

            version = None
            if pkgData.version:
                versionObj = versions.ThawVersion(pkgData.version)
                labels.add(versionObj.branch().label())
                version = str(versionObj.asString())

            flavor = None
            troves.add((name, version, flavor))

        # Get flavors and such.
        foundTroves = set([ x for x in
            itertools.chain(*self._helper.findTroves(troves,
                                                labels=labels).itervalues()) ])

        # get sources for each name version pair
        sources = self._helper.getSourceVersions(foundTroves)

        # collapse to sourceName: [ binNames, ] dictionary
        sourceNameMap = dict([ (x[0].split(':')[0], [ z[0] for z in y ])
                               for x, y in sources.iteritems() ])

        binRemovals = set(itertools.chain(*[ sourceNameMap[x]
                                             for x in removeSource
                                             if x in sourceNameMap ]))

        # take the union
        removals = set(removePackages) | set(removeObsoleted) | binRemovals

        errors = []
        # Make sure these packages are not in the group model.
        for pkgKey, pkgData in group.iteritems():
            if pkgData.name in removals:
                errors.append(pkgData.name)

        if errors:
            log.info('found packages that should be removed %s' % errors)
            raise ExpectedRemovalValidationFailedError(updateId=updateId,
                                                       pkgNames=errors)
