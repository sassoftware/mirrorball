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
from conary.lib.cfgtypes import CfgString, CfgList
from rmake.build.buildcfg import CfgTroveSpec

class UpdateBotConfig(cfg.SectionedConfigFile):
    """
    Config class for updatebot.
    """

    # R0904 - to many public methods
    # pylint: disable-msg=R0904

    # path to configuration files (conaryrc, rmakerc)
    configPath          = CfgString
    commitMessage       = (CfgString, 'Automated commit by updateBot')

    repositoryUrl       = CfgString
    repositoryPaths     = (CfgList(CfgString), ['/'])

    topGroup            = CfgTroveSpec

    excludePackages     = CfgList(CfgString)
    advisoryException   = CfgList(CfgList(CfgString))
