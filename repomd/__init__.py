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


from repomdxml import RepoMdXml
from repository import Repository
from errors import *

__all__ = ('Client', ) + public_errors

class Client(object):
    def __init__(self, repoUrl):
        self._repoUrl = repoUrl

        self._baseMdPath = '/repodata/repomd.xml'
        self._repo = Repository(self._repoUrl)
        self._repomd = RepoMdXml(self._repo, self._baseMdPath).parse()

    def getRepos(self):
        return self._repo

    def getPatchDetail(self):
        node = self._repomd.getRepoData('patches')
        return [ x.parseChildren() for x in node.parseChildren().getPatches() ]

    def getPackageDetail(self):
        node = self._repomd.getRepoData('primary')
        return node.parseChildren().getPackages()
