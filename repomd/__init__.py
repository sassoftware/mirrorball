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
Common repository metadata parsing library.

Handles parsing most yum metadata including SuSE proprietary patch/delta rpm
data.

NOTE: parsing of the following files is not implemented:
    * filelists.xml.gz
    * other.xml.gz
    * product.xml

Example:
> import repomd
> client = repomd.Client(url)
> patches = client.getPatchDetail()
> for patch in patches:
>     # print all of the advisories in the repository
>     print patch.description
"""

from repomd.repomdxml import RepoMdXml
from repomd.repository import Repository
from repomd.errors import RepoMdError, ParseError, UnknownElementError

__all__ = ('Client', 'RepoMdError', 'ParseError', 'UnknownElementError')

class Client(object):
    """
    Client object for extracting information from repository metadata.
    """

    def __init__(self, repoUrl):
        self._repoUrl = repoUrl

        #self._baseMdPath = '/repodata/repomd.xml'
        self._baseMdPath = 'repodata/repomd.xml'
        self._repo = Repository(self._repoUrl)
        self._repomd = RepoMdXml(self._repo, self._baseMdPath).parse()

    def getRepos(self):
        """
        Get a repository instance.
        @return instance of repomd.repository.Repository
        """

        return self._repo

    def getPatchDetail(self):
        """
        Get a list instances representing all patch data in the repository.
        @return [repomd.patchxml._Patch, ...]
        """

        node = self._repomd.getRepoData('patches')

        if node is None:
            return []

        return [ x.parseChildren() for x in node.parseChildren().getPatches() ]

    def getPackageDetail(self):
        """
        Get a list instances representing all packages in the repository.
        @ return [repomd.packagexml._Package, ...]
        """

        node = self._repomd.getRepoData('primary')
        if node is None:
            return []
        return node.parseChildren().getPackages()

    def getFileLists(self):
        """
        Get a list instances representing filelists in the repository.
        @ return [repomd.filelistsxml._Package, ...]
        """
        node = self._repomd.getRepoData('filelists')
        return node.parseChildren().getPackages()

    def getUpdateInfo(self):
        """
        Get a list of instances representing the advisory infomration for
        all updates.
        @return [ repomd.userinfoxml._Update ]
        """

        node = self._repomd.getRepoData('updateinfo')

        if not node:
            return []

        return node.parseChildren().getUpdateInfo()
