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

        self._baseMdPath = '/repodata/repomd.xml'
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
