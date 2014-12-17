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

        @param rebuild: build all packages, even if source package is the same
        @type rebuild: bool
        @param recreate: recreate all source packages
        @type recreate: bool
        """
        start = time.time()
        log.info('starting import')

        # Populate rpm source object from yum metadata.
        self._pkgSource.load()

        # Import sources into repository.
        buildSet, fail = self._updater.create(buildAll=rebuild,
                                              recreate=recreate)

        if fail:
            log.error('failed to create %s packages:' % len(fail))
            for pkg, e in fail:
                log.error('failed to import %s: %s' % (pkg, e))
            return {}, fail

        trvMap = {}

        total = sum(len(chunk) for chunk, _ in buildSet)
        built = 0
        log.info('found %s packages to build' % total)
        for toBuild, resolveTroves in buildSet:
            if len(toBuild):
                # create an initial builder object to get the base rmake config
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
                        trvMap.update(builder.build([nvf for nvf, _ in toBuild]))
                    except JobFailedError:
                        if tries > 1:
                            raise
                        tries += 1
                        log.info('attempting to retry build: %s of %s',
                                 tries, 2)
                    else:
                        break

                log.info('import completed successfully')

                built += len(toBuild)
                log.info('built %s packages of %s', built, total)
        else:
            log.info('no packages found to build, maybe there is a flavor '
                     'configuration issue')
        log.info('elapsed time %s' % (time.time() - start, ))
        return trvMap


class Updater(UpdaterSuperClass):
    """Class for finding and updating packages sourced from artifactory
    """

    def create(self, buildAll=False, recreate=False):
        """Import new packages into the repository

        By default, this will only imort and build completely new packages. Set
        `buildAll` to True if you want to buid all packages, even ones whose
        source trove did not changes. Set `recreate` True if you want to check
        if the source changed, and import it if it has.

        @param buildAll: build all binary packages, even if their source didn't
            change, defaults to False
        @type buildAll: bool
        @param recreate: commit changed source packages when True, else only
            commit new sources
        @type recreate: bool
        @return: a list of buildable chunks (sets of packages that can be built
            together)
        @rtype: [set([((name, version, flavor), pkg), ...]), ...]
        """
        troveList = []
        for p in self._pkgSource.pkgQueue:
            troveList.append((p.name, p.getConaryVersion(), None))
            troveList.append(('%s:source' % p.name, p.getConaryVersion(), None))

        verCache = {}
        for k, v in self._conaryhelper.findTroves(
                troveList,
                allowMissing=True,
                ).iteritems():
            if len(v) > 1:
                import epdb; epdb.st()  # XXX breakpoint
            verCache[k] = v[0][1]  # v is a list of a tuple (name, ver, flav)

        fail = set()
        chunk = set()
        resolveTroves = set()
        toBuild = []
        total = len(self._pkgSource.pkgQueue)

        class counter:
            count = 1

        def addPackage(p, isDep=False):
            version = verCache.get(
                ('%s:source' % p.name, p.getConaryVersion(), None))

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
                        doImport = False
                else:
                    doImport = False

            if doImport:
                try:
                    log.info(
                        'attempting to import %s (%s/%s)',
                        '/'.join(p.getGAV()),
                        counter.count,
                        total,
                        )
                    self._conaryhelper.setJsonManifest(p.name, manifest)
                    version = self._conaryhelper.commit(
                        p.name, commitMessage=self._cfg.commitMessage)
                except Exception as e:
                    fail.add((p, e))
            else:
                log.info(
                    'not importing %s (%s/%s)',
                    '/'.join(p.getGAV()),
                    counter.count,
                    total,
                    )
            counter.count += 1

            binVersion = verCache.get((p.name, p.getConaryVersion(), None))
            if (not binVersion or binVersion.getSourceVersion() != version
                    or buildAll):
                log.info('building %s=%s' % (p.name, version))
                log.debug('adding %s=%s to chunk %s', p.name, version, chunk)
                chunk.add(((p.name, version, None), p))
                if not isDep:
                    return True
            else:
                log.info('not building %s=%s' % (p.name, version))
                if isDep:
                    log.debug('adding %s=%s as a resovle trove' %
                              (p.name, binVersion))
                    resolveTroves.add((p.name, binVersion))
            return False

        def getDependencies(pkg):
            deps = set()
            for dep in pkg.dependencies:
                if dep in self._pkgSource.pkgQueue:
                    deps.add(dep)
                    deps.update(getDependencies(dep))
            return deps

        prevLength = None
        loopCount = 0
        while self._pkgSource.pkgQueue:
            pkg = self._pkgSource.pkgQueue.popleft()
            deps = getDependencies(pkg)
            depNames = [pkg.name] + [d.name for d in deps]
            duplicateDeps = set([n for n in depNames if depNames.count(n) > 1])
            currentPkgNames = [name for (name, _, _), _ in chunk]
            pkgMatch = any(p.name in currentPkgNames
                           for p in [pkg] + list(deps))
            if pkgMatch or duplicateDeps:
                # send to end of queue
                self._pkgSource.pkgQueue.append(pkg)
            else:
                if addPackage(pkg):
                    for dep in deps:
                        addPackage(dep, isDep=True)
                        self._pkgSource.pkgQueue.remove(dep)

            length = len(self._pkgSource.pkgQueue)
            if length == prevLength:
                loopCount += 1

            if len(chunk) >= self._cfg.chunkSize or loopCount > length:
                toBuild.append((chunk, resolveTroves))
                chunk = set()
                resolveTroves = set()
                loopCount = 0
                prevLength = None

            prevLength = length

        if chunk and (chunk, resolveTroves) not in toBuild:
            toBuild.append((chunk, resolveTroves))

        return toBuild, fail
