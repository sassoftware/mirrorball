#
# Copyright (c) 2008-2009 rPath, Inc.
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
from conary.lib.cfgtypes import CfgString, CfgList, CfgRegExp, CfgBool, CfgDict, CfgInt
from conary.lib.cfgtypes import ParseError

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


class CfgContextFlavor(CfgFlavor):
    """
    Class for representing both a flavor context name and a build flavor.
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
                context, flavorStr = splt
                flavor = CfgFlavor.parseString(self, flavorStr)
            return context, flavor
        except versions.ParseError, e:
            raise ParseError, e


class UpdateBotConfigSection(cfg.ConfigSection):
    """
    Config class for updatebot.
    """

    # R0904 - to many public methods
    # pylint: disable-msg=R0904

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

    # The top level binary group, this may be the same as topSourceGroup.
    topGroup            = CfgTroveSpec

    # The top level source group.
    topSourceGroup      = CfgTroveSpec

    # Other labels that are referenced in the group that need to be flattend
    # onto the targetLabel.
    sourceLabel         = (CfgList(CfgBranch), [])

    # Label to promote to
    targetLabel         = CfgBranch

    # Packages other than the topGroup that need to be promoted.
    extraPromoteTroves  = (CfgList(CfgTroveSpec), [])

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
    archContexts        = CfgList(CfgString)

    # flavors to build the source group.
    groupFlavors        = (CfgList(CfgFlavor), [])

    # flavors to build kernels.
    kernelFlavors       = (CfgList(CfgContextFlavor), [])

    # packages other than "kernel" to be built in kernelFlavers
    kernelModules       = (CfgList(CfgString), [])

    # flavors to build packages in for packages that need specific flavoring.
    packageFlavors      = (CfgDict(CfgList(CfgContextFlavor)), {})

    # After committing a rMake job to the repository pull the changeset back out
    # to make sure all of the contents made it into the repository.
    sanityCheckCommits   = (CfgBool, False)

    # Save all binary changesets to disk before committing them.
    saveChangeSets      = (CfgBool, False)

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

    # If sources are not available pkgSource will attempt to build artificial
    # source information if this is set to True.
    synthesizeSources = (CfgBool, False)

    # Number of troves at which to switch to a splitarch build. This is mostly
    # a magic number, but at least it is configurable?
    maxBuildSize = (CfgInt, 10)


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
        if not self.configPath.startswith(os.sep):
            # configPath is relative
            dirname = os.path.dirname(args[0])
            self.configPath = os.path.normpath(os.path.join(dirname,
                                                            self.configPath))
        return ret
