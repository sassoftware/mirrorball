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
Module for interacting with repository metadata.
"""

from updatebot.pkgsource.rpmsource import RpmSource
from updatebot.pkgsource.yumsource import YumSource
from updatebot.pkgsource.debsource import DebSource
from updatebot.pkgsource.errors import UnsupportedRepositoryError

def PackageSource(cfg):
    """
    Method that returns an instance of the appropriate package source
    backend based on config data.
    """

    if cfg.repositoryFormat == 'apt':
        return DebSource(cfg)
    elif cfg.repositoryFormat == 'yum':
        return YumSource(cfg)
    else:
        raise UnsupportedRepositoryError(repo=cfg.repositoryFormat,
                                         supported=['apt', 'yum'])
