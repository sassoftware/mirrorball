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
