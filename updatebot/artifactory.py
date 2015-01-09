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

        if not buildSet:
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
        if existing sources changed, and import them if they have.

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
        # generate a list of trove specs for the packages in the queue so
        # we can populate a cache of existing conary versions
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
                # something weird happened
                import epdb; epdb.st()  # XXX breakpoint
            verCache[k] = v[0][1]  # v is a list of a tuple (name, ver, flav)

        fail = set()  # failed packages and their error messages
        chunk = set()  # chunk of packages to build
        resolveTroves = set()  # resolveTroves for the current chunk
        toBuild = []    # list of chunks to build
        total = len(self._pkgSource.pkgQueue)   # total number of packages

        # this is bit of a hack so that our closures can update the count
        # of packages we have processed
        class counter:
            count = 1

        def addPackage(p):
            """Add package to current chunk

            If the package is new, or `recreate` is True, then check if the
            source needs to be updated.

            If there is no existing binary, or the existing binary's source is
            not the same, then add the package to the current chunk.

            Returns True if the package was added to the chunk, False otherwise
            """
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
                        # manifest didn't change so don't re-import
                        doImport = False
                else:
                    doImport = False

            if doImport:
                try:
                    log.info('attempting to import %s (%s/%s)', p,
                             counter.count, total)
                    self._conaryhelper.setJsonManifest(p.name, manifest)
                    version = self._conaryhelper.commit(
                        p.name, commitMessage=self._cfg.commitMessage)
                except Exception as e:
                    fail.add((p, e))
            else:
                log.info('not importing %s (%s/%s)', p, counter.count, total)
            counter.count += 1

            binVersion = verCache.get((p.name, p.getConaryVersion(), None))
            if (not binVersion or binVersion.getSourceVersion() != version
                    or buildAll):
                log.info('building %s=%s' % (p.name, version))
                log.debug('adding %s=%s to chunk %s', p.name, version, chunk)
                chunk.add(((p.name, version, None), p))
                return True, binVersion
            else:
                log.info('not building %s=%s' % (p.name, version))
                return False, binVersion

        def getDependencies(pkg):
            """Recursively get the dependencies of package 'pkg' and its
            dependencies' dependencies.
            """
            deps = set()
            for dep in pkg.dependencies:
                deps.add(dep)
                deps.update(getDependencies(dep))
            return deps

        # of the packages loaded by pkgSource, we need to import new or updated
        # sources, and build new or updated binaries. We also need to not
        # overload the rmake builds, so we need to break the packages up into
        # managable, dep closed chunks. Additionally, we need to configure
        # resolveTrove entries for each chunk so that rmake can resolve
        # dependencies that are already built
        prevLength = None
        loopCount = 0
        while self._pkgSource.pkgQueue:
            pkg = self._pkgSource.pkgQueue.popleft()
            deps = getDependencies(pkg)

            # if the current package, or any of its dependencies, match a
            # package already in the chunk, then kick the package to the end
            # of the queue. this avoids trying to build two versions of the
            # same package in a single rmake job
            depNames = [pkg.name] + [d.name for d in deps]
            duplicateDeps = set([n for n in depNames if depNames.count(n) > 1])
            currentPkgNames = [name for (name, _, _), _ in chunk]
            pkgMatch = any(p.name in currentPkgNames
                           for p in [pkg] + list(deps))
            if pkgMatch or duplicateDeps:
                # send to end of queue
                self._pkgSource.pkgQueue.append(pkg)
            else:
                # add the package to the chunk.
                if addPackage(pkg):
                    # if the package was added to the chunk, then add its
                    # deps and remove them from the queue
                    self._pkgSource.chunked.add(pkg)
                    for dep in deps:
                        # check if this dep is already in a chunk, and if not
                        # see if its going to be built
                        if dep in self._pkgSource.chunked:
                            depAdded = False
                            depVersion = None
                        else:
                            depAdded, depVersion = addPackage(dep)

                        if not depAdded:
                            # this dep is already built so create resolve trove
                            log.debug('adding %s=%s as a resovle trove' %
                                      (dep.name, depVersion))
                            resolveTroves.add((dep.name, binVersion))

                        # either way this dep is built so remove it from the
                        # queue and add it to the chunked packages
                        if dep in self._pkgSource.pkgQueue:
                            self._pkgSource.pkgQueue.remove(dep)
                            self._pkgSource.chunked.add(dep)

            # if the length of the queue didn't change, then we might be
            # in an infinite loop due to package name conflicts. increment
            # the loop counter
            length = len(self._pkgSource.pkgQueue)
            if length == prevLength:
                loopCount += 1

            # if the chunk is bigger than the max chunk size, or we have
            # looped over every package in the queue, then add the chunk to
            # the build set and start a new one
            if len(chunk) >= self._cfg.chunkSize or loopCount > length:
                toBuild.append((chunk, resolveTroves))
                chunk = set()
                resolveTroves = set()
                loopCount = 0
                prevLength = None

            prevLength = length

        # make sure we add the last chunk to the build set
        if chunk and (chunk, resolveTroves) not in toBuild:
            toBuild.append((chunk, resolveTroves))

        return toBuild, fail
