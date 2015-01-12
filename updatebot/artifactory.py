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
Module for finding artifactory packages and updating them
"""

from collections import deque
import logging
import time

from conary import conarycfg
from rmake.build import buildcfg
from rmake.cmdline import helper

from . import cmdline
from . import pkgsource
from .bot import Bot as BotSuperClass
from .build import Builder
from .errors import JobFailedError
from .lib import util
from .update import Updater as UpdaterSuperClass


log = logging.getLogger('updatebot.artifactory')


class Bot(BotSuperClass):

    _updateMode = 'artifactory'

    def __init__(self, cfg):
        self._validateMode(cfg)

        self._cfg = cfg

        self._clientcfg = cmdline.UpdateBotClientConfig()
        self._ui = cmdline.UserInterface(self._clientcfg)

        self._pkgSource = pkgsource.PackageSource(self._cfg, self._ui)
        self._updater = Updater(self._cfg, self._ui, self._pkgSource)

    def create(self, rebuild=False, recreate=None):
        """
        Do initial imports.

        :param bool rebuild: build all packages, even if source is the same
        :param bool recreate: recreate all source packages
        """
        start = time.time()
        log.info('starting import')

        # Populate rpm source object from yum metadata.
        self._pkgSource.load()

        # Import sources into repository.
        trvMap, fail = self._updater.create(buildAll=rebuild, recreate=recreate)

        if fail:
            log.error('failed to create %s packages:' % len(fail))
            for pkg, e in fail:
                log.error('failed to import %s: %s' % (pkg, e))
            return {}, fail

        log.info('elapsed time %s' % (time.time() - start, ))
        return trvMap, fail


class Updater(UpdaterSuperClass):
    """Class for finding and updating packages sourced from artifactory
    """

    def _createVerCache(self, troveList):
        verCache = {}
        for k, v in self._conaryhelper.findTroves(
                troveList,
                allowMissing=True,
                ).iteritems():
            if len(v) > 1:
                # something weird happened
                import epdb; epdb.st()  # XXX breakpoint
            verCache[k] = v[0][1]  # v is a list of a tuple (name, ver, flav)
        return verCache

    def _build(self, buildSet, cache):
        """Helper function to do some repetivite pre-build processing

        :param buildSet: list of name, version, flavor tuples and packages to
            build
        :type buildSet: [((name, version, flavor), package), ...]
        :param dict cache: conary version cache
        """
        # unpack buildSet into nvf tuples and packages lists
        nvfs, packages = zip(*buildSet)

        resolveTroves = set()
        # create resolve troves for deps not in the current chunk
        for pkg in packages:
            needResolveTroves = set(pkg.dependencies) - set(packages)
            for p in needResolveTroves:
                currentVersion = cache.get(
                    (p.name, p.getConaryVersion(), None))
                resolveTroves.add((p.name, currentVersion))

        rmakeCfg = Builder(self._cfg, self._ui)._getRmakeConfig()
        if resolveTroves is not None:
            # add our resolveTroves to the build config
            rmakeCfg.configKey(
                'resolveTroves',
                ' '.join('%s=%s' % r for r in resolveTroves),
                )

        # make a new buidler with rmakeCfg to do the actual build
        builder = Builder(self._cfg, self._ui, rmakeCfg=rmakeCfg)

        # Build all newly imported packages.
        tries = 0
        while True:
            try:
                trvMap = builder.build(nvfs)
            except JobFailedError:
                if tries > 1:
                    raise
                tries += 1
                log.info('attempting to retry build: %s of %s', tries, 2)
            else:
                break

        return trvMap

    def _importPackage(self, p, version, recreate):
        """Import source package

        If the package is new, or `recreate` is True, then check if the
        source needs to be updated.

        :param PomPackage p: package to import
        :param version: conary version of existing source
        :type version: conary version object or None
        :param bool recreate: re-import the package if True
        :returns: True if the package was imported, False otherwise
        :rtype: bool
        """
        manifest = dict(
            version=p.getConaryVersion(),
            build_requires=p.buildRequires,
            artifacts=p.artifacts,
            )

        doImport = True
        if version:
            # source exists, see if we should re-commit
            if recreate:
                # check if build reqs or artifacts changed
                oldManifest = self._conaryhelper.getJsonManifest(
                    p.name, version)
                oldBuildReqs = sorted(oldManifest.get('build_requires', []))
                oldArtifacts = sorted(oldManifest.get('artifacts', []))
                buildReqs = sorted(manifest['build_requires'])
                artifacts = sorted(manifest['artifacts'])
                if (buildReqs == oldBuildReqs
                        and artifacts == oldArtifacts):
                    # manifest didn't change so don't re-import
                    doImport = False
            else:
                doImport = False

        if doImport:
            log.info("attempting to import %s", p)
            self._conaryhelper.setJsonManifest(p.name, manifest)
            version = self._conaryhelper.commit(
                p.name, commitMessage=self._cfg.commitMessage)
        else:
            log.info("not importing %s", p)

        return version

    def create(self, buildAll=False, recreate=False):
        """Import new packages into the repository

        By default, this will only imort and build completely new packages. Set
        `buildAll` to True if you want to buid all packages, even ones whose
        source trove did not changes. Set `recreate` True if you want to check
        if existing sources changed, and import them if they have.

        :param buildAll: build all binary packages, even if their source didn't
            change, defaults to False
        :type buildAll: bool
        :param recreate: commit changed source packages when True, else only
            commit new sources
        :type recreate: bool
        :returns: a list of buildable chunks (sets of packages that can be built
            together)
        :rtype: [set([((name, version, flavor), pkg), ...]), ...]
        """
        # generate a list of trove specs for the packages in the queue so
        # we can populate a cache of existing conary versions
        troveList = []
        for p in self._pkgSource.pkgQueue:
            troveList.append((p.name, p.getConaryVersion(), None))
            troveList.append(('%s:source' % p.name, p.getConaryVersion(), None))

        fail = set()                    # packages that failed to import
        chunk = set()                   # current chunk of packages to build
        chunkedPackageNames = set()     # names of packages in the current chunk
        trvMap = {}                     # map of built troves
        verCache = self._createVerCache(troveList)  # initial version cache

        for pkg in self._pkgSource.pkgQueue:
            if pkg.name in chunkedPackageNames \
                    or len(chunk) >= self._cfg.chunkSize:
                # chunk contains a package with the same name or is too big
                # so build the current chunk before continuing
                trvMap.update(self._build(chunk, verCache))

                # update the version cache
                verCache = self._createVerCache(troveList)

                # clear the chunk
                chunk = set()
                chunkedPackageNames = set()

            srcVersion = verCache.get((
                '%s:source' % pkg.name,
                pkg.getConaryVersion(),
                None,
                ))
            binVersion = verCache.get((
                pkg.name,
                pkg.getConaryVersion(),
                None,
                ))

            # determine if pkg needs to be imported, and update srcVersion
            try:
                srcVersion = self._importPackage(pkg, srcVersion, recreate)
            except Exception, e:
                log.error('failed to import %s: %s' % (pkg, e))
                fail.add((pkg, e))

            # if buildAll is true, or there is no existing binary or the binary
            # was built from a different source, then build pkg
            if (buildAll or not binVersion
                     or binVersion.getSourceVersion() != srcVersion):
                log.info('building %s' % pkg)
                log.debug('adding %s to chunk %s', pkg, chunk)
                chunk.add(((pkg.name, srcVersion, None), pkg))
                chunkedPackageNames.add(pkg.name)
            else:
                log.info('not building %s' % pkg)

        else:
            # exhausted the list, so make sure we build the last chunk
            if chunk:
                trvMap.update(self._build(chunk, verCache))

        return trvMap, fail
