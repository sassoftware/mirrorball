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
Configuration module for updatebot.
"""

from conary.lib import cfg
from conary import versions
from conary.conarycfg import CfgFlavor, CfgLabel
from conary.lib.cfgtypes import CfgString, CfgList, CfgRegExp, ParseError

from rmake.build.buildcfg import CfgTroveSpec

class CfgBranch(CfgLabel):
    """
    Class for representing conary branches.
    """

    def parseString(self, val):
        """
        Parse config string.
        """

        try:
            versions.Branch(val)
        except versions.ParseError, e:
            raise ParseError, e


class UpdateBotConfig(cfg.SectionedConfigFile):
    """
    Config class for updatebot.
    """

    # R0904 - to many public methods
    # pylint: disable-msg=R0904

    # name of the product to use in advisories
    productName         = CfgString

    # path to configuration files (conaryrc, rmakerc)
    configPath          = CfgString

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
    targetLabel         = CfgLabel

    # Packages to import
    package             = (CfgList(CfgString), [])

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

    # list of contexts that all packages are built in.
    archContexts        = CfgList(CfgString)

    # flavors to build the source group.
    groupFlavors        = (CfgList(CfgFlavor), [])

    # email information for sending advisories
    emailFromName       = CfgString
    emailFrom           = CfgString
    emailTo             = (CfgList(CfgString), [])
    emailBcc            = (CfgList(CfgString), [])
    smtpServer          = CfgString
