#
# Copyright (c) 2008-2010 rPath, Inc.
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
Configuration module for updatebot.
"""

import os

from conary.lib import cfg
from conary import versions
from conary.conarycfg import CfgFlavor, CfgLabel
from conary.lib.cfgtypes import ParseError
from conary.lib.cfgtypes import CfgInt, CfgQuotedLineList
from conary.lib.cfgtypes import CfgString, CfgList, CfgRegExp, CfgBool, CfgDict

from rmake.build.buildcfg import CfgTroveSpec

from updatebot.lib import util

class CfgBranch(CfgLabel):
    """
    Class for representing conary branches.
    """

    def parseString(self, val):
        """
        Parse config string.
        """

        try:
            return versions.VersionFromString(val)
        except versions.ParseError, e:
            raise ParseError, e


class CfgStringFlavor(CfgFlavor):
    """
    Class for representing a three tuple of a string and an optional flavor.
    """

    def parseString(self, val):
        """
        Parse config string.
        """

        try:
            splt = val.split()
            if len(splt) == 1:
                context = val
                flavor = None
            else:
                context = splt[0]
                flavorStr = ' '.join(splt[1:])
                flavor = CfgFlavor.parseString(self, flavorStr)
            return context, flavor
        except versions.ParseError, e:
            raise ParseError, e


class CfgStringFlavorUse(CfgStringFlavor):
    """
    Class for represnting a three tuple of string and an optional flavor and
    use flag.
    """

    def parseString(self, val):
        """
        Parse config string.
        """

        use = None
        splt = val.split()
        if len(splt) > 1:
            use = splt[-1]
            val = ' '.join(splt[:-1])

        context, flavor = CfgStringFlavor.parseString(self, val)
        return context, flavor, use

class CfgFlavorFilter(CfgRegExp, CfgFlavor):
    """
    Class for parsing (context, flavor, regex) tuples, where flavor and
    regex are optional (during parsing, though not necessarily in
    implementation).
    """

    def parseString(self, val):
        """
        Parse config input.
        """

        try:
            splt = val.split(None, 2)
            if len(splt) == 1:
                context = val
                flavor = None
                fltr = None
            elif len(splt) == 2:
                context = splt[0]
                # Note: this split can't handle flavors containing spaces...
                flavorStr = splt[1]
                flavor = CfgFlavor.parseString(self, flavorStr)
                fltr = None
            else:
                context = splt[0]
                flavorStr = splt[1]
                flavor = CfgFlavor.parseString(self, flavorStr)
                # ...but it *can* handle regexes containing spaces:
                fltrStr = ' '.join(splt[2:])
                fltr = CfgRegExp.parseString(self, fltrStr) 
            return context, flavor, fltr
        except versions.ParseError, e:
            raise ParseError, e


class CfgStringFilter(CfgRegExp):
    """
    Class for parsing (string, regex) tuples.
    """

    def parseString(self, val):
        """
        Parse config input.
        """

        try:
            splt = val.split()
            if len(splt) == 1:
                context = val
                fltr = None
            else:
                context, fltrStr = splt
                fltr = CfgRegExp.parseString(self, fltrStr)
            return context, fltr
        except versions.ParseError, e:
            raise ParseError, e


class CfgAdvisoryOrder(CfgString):
    """
    Class for parsing advisor order config.
    """

    def parseString(self, val):
        splt = val.split()
        assert len(splt) == 3
        fromId, toId, advisory = splt
        fromId = int(fromId)
        toId = int(toId)
        return fromId, toId, advisory


class CfgSourceOrder(CfgString):
    """
    Class for parsing source order config.
    """

    def parseString(self, val):
        splt = val.split()
        assert len(splt) == 7
        fromId, toId = splt[:2]
        fromId = int(fromId)
        toId = int(toId)
        nevra = tuple(splt[2:])
        return fromId, toId, nevra


class CfgNevra(CfgString):
    """
    Class for parsing nevras
    """

    def parseString(self, val):
        splt = tuple(val.split())
        assert len(splt) == 5
        return splt


class CfgNevraTuple(CfgString):
    """
    Class for parsing obsolete mappings:
    <obsoleting nevra> <obsoleted nevra>
    """

    def parseString(self, val):
        splt = val.split()
        assert len(splt) == 10
        obsoleter = tuple(splt[0:5])
        obsoleted = tuple(splt[5:10])
        return obsoleter, obsoleted


class CfgIntDict(CfgDict):
    """
    Config class to represent dictionaries keyed by integers rather than
    strings.
    """

    def updateFromString(self, val, str):
        # update the dict value -- don't just overwrite it, it might be
        # that the dict value is a list, so we call updateFromString
        strs = str.split(None, 1)
        if len(strs) == 1:
            dkey, dvalue = strs[0], ''
        else:
            (dkey, dvalue) = strs

        dkey = CfgInt().parseString(dkey)

        if dkey in val:
            val[dkey] = self.valueType.updateFromString(val[dkey], dvalue)
        else:
            val[dkey] = self.parseValueString(dkey, dvalue)
        return val

    def toStrings(self, value, displayOptions):
        value = dict([ (str(x), y) for x, y in value.iteritems() ])
        return CfgDict.toStrings(self, value, displayOptions)


class CfgStringFourTuple(CfgString):
    """
    Config class to represent a three tuple of strings.
    """

    def parseString(self, val):
        splt = val.split()
        if len(splt) != 4:
            raise ParseError
        vals = []
        for val in splt:
            vals.append(CfgString.parseString(self, val))
        return tuple(vals)


class UpdateBotConfigSection(cfg.ConfigSection):
    """
    Config class for updatebot.
    """

    # R0904 - to many public methods
    # pylint: disable-msg=R0904

    # Mode that updatebot is running in. (possible values ar
    # 'ordered' and 'latest'.
    updateMode          = CfgString

    # name of the product to use in advisories
    productName         = CfgString

    # platform short name
    platformName        = CfgString

    # upstream product version
    upstreamProductVersion = CfgString

    # disables checks for update completeness, this should only be enabled if
    # you know what you are doing and have a good reason.
    disableUpdateSanity = CfgBool

    # path to configuration files relative to updatebotrc (conaryrc, rmakerc)
    configPath          = (CfgString, './')

    # type of upstream repostory to pull packages from, supported are apt
    # and yum.
    repositoryFormat    = (CfgString, 'yum')

    # Default commit message to use when committing to the repository.
    commitMessage       = (CfgString, 'Automated commit by updateBot')

    # Url to the yum repository
    repositoryUrl       = CfgString

    # Paths based off of the repositoryUrl to get to individual repositories.
    repositoryPaths     = (CfgList(CfgString), ['/'])

    # Treat any path matching this spec as "base" (ISO) content.
    # In other words, these packages are the golden bits, not errata.
    repositoryBasePaths = (CfgList(CfgRegExp), [])

    # Arch strings for each repository to signify what base architecture each
    # repository is meant for.
    # repositoryName archString
    repositoryArch      = (CfgDict(CfgString), {})

    # Add a package to a particular repository. This is useful for adding x86
    # packages to an x86_64 group. Normally in the form: pkgName conaryVersion
    # archStr repositoryArch
    repositoryPackage   = (CfgList(CfgStringFourTuple), [])

    # Associate binaries generated from a nosrc package with a source package
    # name if the nosrc package matches a given regular expression.
    nosrcFilter         = (CfgList(CfgStringFilter), [])

    # Ignore packages with "32bit" in the name. This is intened for use with
    # SLES based platforms.
    ignore32bitPackages = (CfgBool, False)

    # Data source for determining platform version information, only used for
    # group versioning.
    versionSources      = (CfgDict(CfgString), {})

    # The top level binary group, this may be the same as topSourceGroup.
    topGroup            = CfgTroveSpec

    # The top level source group.
    topSourceGroup      = CfgTroveSpec

    # Parent top level source group
    topParentSourceGroup = CfgTroveSpec

    # Path to search for packages to be included in the platform.
    platformSearchPath  = (CfgQuotedLineList(CfgLabel), [])

    # Group contents info.
    groupContents       = (CfgDict(CfgDict(CfgString)), {})

    # Other labels that are referenced in the group that need to be flattend
    # onto the targetLabel.
    sourceLabel         = (CfgList(CfgBranch), [])

    # Label to promote to
    targetLabel         = CfgBranch

    # Packages other than the topGroup that need to be promoted.
    extraPromoteTroves  = (CfgList(CfgTroveSpec), [])

    # Extra packages that are expected to be in the promote result set at a
    # given bucketId. These are normally packages that for some reason or
    # another, usually deps, we had to rebuild.
    extraExpectedPromoteTroves = (CfgIntDict(CfgList(CfgTroveSpec)), {})

    # List of source packages for which we expect manifest differences
    # between parent and child platform. When differences are found,
    # create a new package on the child label, overriding the
    # parent-platform package/manifest.
    expectParentManifestDifferences = (CfgList(CfgString), [])

    # For debugging the above--use with caution!
    ignoreAllParentManifestDifferences = (CfgBool, False)

    # Packages to import
    package             = (CfgList(CfgString), [])

    # Include all packages, if this is set to true packages becomes an
    # exclude list.
    packageAll          = (CfgBool, False)

    # Factory to use for importing
    newPackageFactory   = (CfgString, None)

    # Package to exclude from all updates, these are normally packages that
    # are not managed as part of this distro (ie. in sles we pull some
    # packages from rpl:1).
    excludePackages     = (CfgList(CfgString), [])

    # Exclude these archs from the rpm source.
    excludeArch         = (CfgList(CfgString), [])

    # Disable advisories all together.
    disableAdvisories   = (CfgBool, False)

    # Packages for which there might not reasonably be advisories. Define a
    # default advisory message to send with these packages.
    advisoryException   = (CfgList(CfgList(CfgString)), [])

    # Filter out patches with matching descriptions or summaries.
    patchFilter         = (CfgList(CfgRegExp), [])

    # url to base archive searchs off of
    listArchiveBaseUrl  = CfgString

    # date to start querying archives
    listArchiveStartDate = CfgString

    # list of contexts that all packages are built in.
    archContexts        = CfgList(CfgStringFilter)

    # flavors to build the source group.
    groupFlavors        = (CfgList(CfgFlavor), [])

    # flavors to build kernels.
    kernelFlavors       = (CfgList(CfgStringFlavor), [])

    # packages other than "kernel" to be built in kernelFlavers
    kernelModules       = (CfgList(CfgString), [])

    # flavors to build packages in for packages that need specific flavoring.
    packageFlavors      = (CfgDict(CfgList(CfgStringFlavor)), {})

    # 3-tuple of (context, flavor, regex) of arch-specific package
    # flavors to omit unless the regex matches a binary package in the
    # manifest.  Useful for omitting built of otherwise-expected flavors
    # when a package is missing from the repository.
    packageFlavorsMissing = (CfgDict(CfgList(CfgFlavorFilter)), {})

    # After committing a rMake job to the repository pull the changeset back out
    # to make sure all of the contents made it into the repository.
    sanityCheckCommits   = (CfgBool, False)

    # Check the changeset for any rpm capsules and validate that the changeset
    # contents match the rpm header. Implies saveChangeSets.
    sanityCheckChangesets = (CfgBool, False)

    # Save all binary changesets to disk before committing them.
    saveChangeSets      = (CfgBool, False)

    # Always build this list of package names in one job rather than splitting
    # them up in the case that you are using a builder that splits by default.
    combinePackages     = (CfgList(CfgQuotedLineList(CfgString)), [])

    # email information for sending advisories
    emailFromName       = CfgString
    emailFrom           = CfgString
    emailTo             = (CfgList(CfgString), [])
    emailBcc            = (CfgList(CfgString), [])
    smtpServer          = CfgString

    # Jira Info
    jiraUser            = CfgString
    jiraPassword        = CfgString
    jiraUrl             = CfgString
    jiraSecurityGroup   = CfgString

    # Satis Info
    satisUrl            = CfgString

    # Try to build from source rpms
    buildFromSource     = (CfgBool, False)

    # Write package metadata to the source trove no matter the source
    # package format.
    writePackageMetadata = (CfgBool, False)

    # Write version information to the source trove, generated from the source
    # version and revision.
    writePackageVersion = (CfgBool, False)

    # If sources are not available pkgSource will attempt to build artificial
    # source information if this is set to True.
    synthesizeSources = (CfgBool, False)

    # Number of troves at which to switch to a splitarch build. This is mostly
    # a magic number, but at least it is configurable?
    maxBuildSize = (CfgInt, 10)

    # Map of updateIds to upstream versions to use if you don't want to use the
    # normal versioning scheme.
    upstreamVersionMap = (CfgIntDict(CfgString), {})

    # List of errata timestamps to merge together. This is used when one errata
    # leaves the platform in a non dependency closed state and a later update
    # should solve the dependency problem. All updates are folded into the first
    # bucket listed.
    mergeUpdates = (CfgList(CfgQuotedLineList(CfgInt)), [])

    # Sometimes, we synthesize a source for a nosrc rpm, because we
    # really don't know any better.  When we find out that, in fact,
    # the nosrc rpm belongs to a src rpm with a _different_ version,
    # the only way to resolve it is by an explicit merging of the two 
    # source packages.
    mergeSources = (CfgList(CfgNevraTuple), [])

    # Timestamp of first erratum.  This is used as a baseline for
    # determining if any update packages are missing errata.  It should
    # auto-detect correctly, but in some cases--for instance, when a
    # distribution releases the same package as a baseline package on
    # one channel and an update on a parallel channel--this will require
    # manual specification.
    firstErrata = CfgInt

    # Timestamp of last erratum.  This is used to stop errata processing
    # at a specified timestamp, which is useful if recent errata are
    # broken and some sort of catch-up run is being done.
    lastErrata = CfgInt
    
    # Timestamp after which errata promotions begin.  This is useful in
    # cases where the baseline distribution must be split across
    # multiple updateId's in order to de-dupe the package list.
    errataPromoteAfter = (CfgInt, 0)

    # Errata timestamp pairs for rescheduling when updates are applied. The
    # first element is the current timestamp of the update. The second element
    # is the new timestamp. You may need to use this option if it appears that
    # the upstream provider has somehow managed to release updates out of order
    # and has caused dependency closure problems. Note that you will need to
    # mark remove anything that has been committed past the destination
    # timestamp to get mirrorball to go back and apply this update.
    reorderUpdates = (CfgList(CfgQuotedLineList(CfgInt)), [])

    # fromUpdateId toUpdateId advisory
    # Sometimes advisories are released out of order, but it is inconvienent to
    # move the entire update bucket.
    reorderAdvisory = (CfgList(CfgAdvisoryOrder), [])

    # advisory trovespec
    extendAdvisory = (CfgDict(CfgList(CfgTroveSpec)), {})

    # fromUpdateId toUpdateId sourceNevra
    # Sometimes multiple versions of the same package are released as part of a
    # single advisory. This does not fit the conary model of doing things, so we
    # have to reschedule one or more of these sources to another time so that
    # they end up in a binary group and get updated in the correct order.
    reorderSource = (CfgList(CfgSourceOrder), [])

    # reuse old revisions as used in SLES, where if on a rebuild with the
    # same version but different revision a subpackage does not change
    # content, the new build is not used
    reuseOldRevisions = (CfgBool, False)

    # updateId binaryPackageName
    # Dictionary of bucketIds and packages that are expected to be removed.
    updateRemovesPackages = (CfgIntDict(CfgList(CfgString)), {})

    # updateId binaryPackageName
    # Dictionary of bucketIds and packages that are expected to be moved
    # between sources.
    updateReplacesPackages = (CfgIntDict(CfgList(CfgString)), {})

    # updateId sourceNevra
    # As of updateId, remove source package specified by sourceNevra
    # from the package model
    removeSource = (CfgIntDict(CfgList(CfgNevra)), {})

    # updateId sourceNevra
    # As of updateId, remove resulting binaries from source package 
    # specified by sourceNevra used when new pkg exists but has different
    # srpm than older pkg
    removeObsoletedSource = (CfgIntDict(CfgList(CfgNevra)), {})

    # updateId sourceNevra
    # At updateId, ignore the source package update specified by
    # sourceNevra and continue to use whatever previous version was in
    # the model.
    ignoreSourceUpdate = (CfgIntDict(CfgList(CfgNevra)), {})

    # updateId sourceNevra
    # At updateId, allow the source package (and any related binary
    # packages) specified by sourceNevra to be missing from the
    # repository. Useful for working around selected gaps uncovered by
    # OrderedBot._checkMissingPackages() during updates or promotes.
    allowMissingPackage = (CfgIntDict(CfgList(CfgNevra)), {})

    # updateId binaryNevra
    # As of updateId, I expect the code to think this nevra should be removed,
    # but I want to keep it.
    keepRemoved = (CfgIntDict(CfgList(CfgNevra)), {})

    # updateId sourceNevra
    # As of updateId, the specified src is fully obsoleted, but
    # should be retained in groups
    keepObsoleteSource = (CfgList(CfgNevraTuple), [])

    # Some obsoletes are merely conceptual preferences, and should not
    # turn into removals.
    # We would prefer CfgSet(CfgTuple(CfgNevra, CfgNevra), set())
    # but CfgSet and CfgTuple do not exist at this point;
    # maybe we can add them later.
    # keepObsolete <obsoleting nevra> <obsoleted nevra>
    keepObsolete = (CfgList(CfgNevraTuple), [])

    # updateId packageName [packageName ...]
    # remove obsoleted packages when other subpackages of the same
    # srpm are not obsoleted, so we cannot use removeSource
    removeObsoleted = (CfgIntDict(CfgList(CfgString)), {})

    # List of broken errata that have been researched and should be ignored
    # when reporting errors.
    brokenErrata = (CfgDict(CfgList(CfgNevra)), {})

    # Dictionary of updateId to list of trove specs. When the bucketId has been
    # reached, update to the version specified in the trovespec rather than the
    # latest that matches the current rpm version.
    useOldVersion = (CfgIntDict(CfgList(CfgTroveSpec)), {})

    # Add a package to a specific group
    addPackage = (CfgIntDict(CfgDict(CfgList(CfgStringFlavorUse))), {})

    # Remove a package from a specific group
    removePackage = (CfgIntDict(CfgDict(CfgList(CfgStringFlavorUse))), {})

    # Group name for group that contains all packages in a platform.
    packageGroupName = (CfgString, 'group-packages')

    # Allow updates for a given nevra to be published without matching errata.
    allowMissingErrata = (CfgList(CfgNevra), [])

    # Allow updates to have versions that go backwards.
    # updateId: [ (from srcTrvSpec, to srcTrvSpec), ... ]
    allowPackageDowngrades = (CfgIntDict(CfgList(CfgNevraTuple)), {})

    # Allow updates which don't include all binary packages corresponding
    # to a given source.
    allowRemovedPackages = (CfgBool, False)

    # Add a source to a specific updateId. This is used to move updates forward
    # after allowing an update to downgrade the version.
    addSource = (CfgIntDict(CfgList(CfgNevra)), {})


class UpdateBotConfig(cfg.SectionedConfigFile):
    """
    Config object for UpdateBot.
    """

    _defaultSectionType = UpdateBotConfigSection

    def __init__(self):
        cfg.SectionedConfigFile.__init__(self)
        for info in self._defaultSectionType._getConfigOptions():
            if info[0] not in self:
                self.addConfigOption(*info)

    def read(self, *args, **kwargs):
        """
        Read specified file.
        """

        # If there is a global config, load it first.
        cfgDir = os.path.dirname(args[0])
        cfgFile = util.join(cfgDir, '../', 'updatebotrc')
        if os.path.exists(cfgFile):
            cfg.SectionedConfigFile.read(self, cfgFile, **kwargs)

        # Find configPath.
        ret = cfg.SectionedConfigFile.read(self, *args, **kwargs)
        if (not self.configPath.startswith(os.sep) and
            args[0].endswith('updatebotrc')):
            # configPath is relative
            dirname = os.path.dirname(args[0])
            self.configPath = os.path.normpath(os.path.join(dirname,
                                                            self.configPath))
        return ret
