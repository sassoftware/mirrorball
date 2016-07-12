#
# Copyright (c) SAS Institute, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#


"""
Module for interacting with repository metadata.
"""

from updatebot.pkgsource.pomsource import PomSource
from updatebot.pkgsource.rpmsource import RpmSource
from updatebot.pkgsource.yumsource import YumSource
from updatebot.pkgsource.errors import UnsupportedRepositoryError


def PackageSource(cfg, ui):
    """
    Method that returns an instance of the appropriate package source
    backend based on config data.
    """

    if cfg.repositoryFormat == 'yum':
        return YumSource(cfg, ui)
    elif cfg.repositoryFormat == 'artifactory':
        return PomSource(cfg, ui)
    elif cfg.repositoryFormat == 'pkgcache':
        from updatebot.pkgsource.pkgcache import PkgCache
        return PkgCache(cfg, ui)
    else:
        raise UnsupportedRepositoryError(repo=cfg.repositoryFormat,
                                         supported=['artifactory', 'yum'])
