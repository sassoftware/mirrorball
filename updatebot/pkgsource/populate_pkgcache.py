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

import os
import hashlib

import prism_rest_client
from prism_rest_client.lib.util import AttrDict

from updatebot import cmdline
from updatebot import pkgsource

import logging
log = logging.getLogger('updatebot.pkgsource.populate_pkgcache')

# Turn down the logging level on requeests
requests_logger = logging.getLogger('requests.packages.urllib3.connectionpool')
requests_logger.setLevel(logging.WARN)

def _srtSources(a, b):
    if a.nevra.arch == 'src' and b.nevra.arch == 'src':
        return 0
    elif a.nevra.arch == 'src':
        return -1
    else:
        return 1

class PkgCacheLoader(object):
    def __init__(self, cfg):
        self._cfg = cfg
        ui = cmdline.UserInterface()
        self.pkgSource = pkgsource.PackageSource(cfg, ui)
        self.api = prism_rest_client.open(cfg.pkgcacheUri)

    def load(self):
        self.loadPkgSource()
        self.parsePkgSourceData()
        self.loadPkgCache()

    def loadPkgSource(self):
        self.pkgSource.load()

    def parsePkgSourceData(self):
        # Find repositories:
        repos = {}
        for path in self.pkgSource._cfg.repositoryPaths:
            arch = self.pkgSource._cfg.repositoryArch.get(path, 'src')
            repos[path] = AttrDict({
                'name': path,
                'arch': arch,
            })

        packages = {}
        sourcePackages = {}
        for path, pkg in self.pkgSource.locationMap.iteritems():
            repo = self._findRepo(pkg, repos)

            p = self._convertPackage(pkg)

            if p.nevra.arch != 'src':
                srcPkg = self.pkgSource.binPkgMap.get(pkg)
                p.sourcepkg = AttrDict({
                    'location': srcPkg.location,
                    'hash': self._getChecksum(srcPkg),
                })

                packages.setdefault(repo.name, list()).append(p)
            else:
                sourcePackages.setdefault(repo.name, list()).append(p)

        self._repos = repos
        self._packages = packages
        self._sourcePackages = sourcePackages

    def _convertPackage(self, pkg):
        _pkg = AttrDict({
                'location': pkg.location,
                'hash': self._getChecksum(pkg),
                'nevra': AttrDict({
                    'name': pkg.name,
                    'epoch': pkg.epoch,
                    'version': pkg.version,
                    'release': pkg.release,
                    'arch': pkg.arch,
                }),
            })

        if hasattr(pkg, 'buildRequires') and pkg.buildRequires:
            _pkg.setdefault('keyvalues', AttrDict())['buildRequires'] = \
                    ','.join(pkg.buildRequires)

        if hasattr(pkg, 'artifacts') and pkg.artifacts:
            _pkg.setdefault('keyvalues', AttrDict())['artifacts'] = \
                    ','.join(a['downloadUri'] for a in pkg.artifacts)

        return _pkg

    def _getChecksum(self, pkg):
        return (pkg.checksum or hashlib.sha256(pkg.location + pkg.name +
            pkg.epoch + pkg.version + pkg.release + pkg.arch).hexdigest())

    def _findRepo(self, pkg, repos):
        """
        Find the best repository for a given package.
        """

        # Handle everything that has a proper location first.
        for path, repo in repos.iteritems():
            if pkg.location.startswith(path):
                return repo

        if pkg.arch == 'src':
            bins = self.pkgSource.srcPkgMap.get(pkg, [])
            binrepos = dict([ (y.name, y) for y in [ self._findRepo(x, repos)
                for x in bins if x.arch != 'src'] ])

            commonPath = self._findCommonPath(binrepos)
            for path, repo in repos.iteritems():
                if repo.arch != 'src':
                    continue
                if path.startswith(commonPath):
                    return repo

            # If no source repositories are found, use the first binary
            # repository.
            return binrepos[sorted(binrepos)[0]]

        assert False


    def _findCommonPath(self, paths):
        """
        Find the path that common amongst all paths involved.
        """

        paths = [ [ y for y in x.split(os.path.sep) if y ] for x in paths ]
        commonPath = []
        idx = 0
        maxIdx = min([ len(x) for x in paths ])
        found = False
        while not found:
            elements = set([ x[idx] for x in paths ])
            if len(elements) > 1 or idx + 1 == maxIdx:
                found = True
            else:
                commonPath.append(list(elements)[0])
                idx += 1
        return os.path.sep.join(commonPath)

    def loadPkgCache(self):
        log.info('creating transaction')
        t = self.api.transactions.append({})

        self.api._cache.client.headers = {
            'X-TransactionId': t.transaction_id,
        }

        name = self._cfg.platformName
        version = self._cfg.upstreamProductVersion

        distros = self.api.distros
        if (name, version) not in [ (x.name, x.version) for x in distros ]:
            distro = distros.append({
                'name': name,
                'version': version,
            })
        else:
            distro = dict(((x.name, x.version), x) for x in distros).get(
                    (name, version))

        self._loadPkgCache(distro, self._sourcePackages)
        self._loadPkgCache(distro, self._packages)

        log.info('committing transaction')
        t.committed = True
        t.persist()

    def _loadPkgCache(self, distro, packages):
        distro_repos = distro.repos
        repos = dict((x.name, x) for x in distro_repos)

        for name, obj in self._repos.iteritems():
            if name in repos:
                repo = repos[name]
                log.info('fetching package hashes for %s' % name)
                pkg_hashes = repo.package_hashes.hashes
            else:
                log.info('adding repository %s' % name)
                repo = distro_repos.append(obj)
                pkg_hashes = []

            for pkg in packages.get(name, []):
                if pkg.hash in pkg_hashes:
                    log.info('found package in cache %s' % pkg.nevra.name)
                    continue

                p = repo.packages.append(pkg)
                log.info('adding %(name)s, %(epoch)s, %(version)s, '
                    '%(release)s, %(arch)s to ' % p.nevra._data + repo.name)
