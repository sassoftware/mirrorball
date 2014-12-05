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

from rmake.build import buildcfg
from rmake.cmdline import helper

from . import cmdline
from . import pkgsource
from .bot import Bot as BotSuperClass
from .build import Builder as BuilderSuperClass
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
        self._builder = Builder(self._cfg, self._ui)

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

        for toBuild, resolveTroves in buildSet:
            if len(toBuild):
                log.info('found %s packages to build' % len(toBuild))

                # Build all newly imported packages.
                failed = self._builder.build(toBuild, resolveTroves)
                log.info('failed to import %s packages' % len(failed))
                if len(failed):
                    for pkg in failed:
                        log.warn('%s' % (pkg, ))
                log.info('import completed successfully')
                log.info('imported %s source packages' % (len(toBuild), ))
        else:
            log.info('no packages found to build, maybe there is a flavor '
                     'configuration issue')

        log.info('elapsed time %s' % (time.time() - start, ))
        return failed


class Builder(BuilderSuperClass):
    """
    Class for wrapping the rMake api until we can switch to using rBuild.

    @param cfg: updateBot configuration object
    @type cfg: config.UpdateBotConfig
    @param ui: command line user interface.
    @type ui: cmdline.ui.UserInterface
    """

    def __init__(self, *args, **kwargs):
        super(Builder, self).__init__(*args, **kwargs)
        self._rmakeCfgFn = kwargs.get('rmakeCfgFn')

    def _formatInput(self, troveSpecs):
        return super(Builder, self)._formatInput([nvf for nvf, _ in troveSpecs])

    def _getRmakeConfig(self, rmakeCfgFn=None, extraResolveTroves=None):
        """Generate an rmake config object

        Get default pluginDirs from the rmake cfg object, setup the plugin
        manager, then create a new rmake config object so that rmakeUser
        will be parsed correctly. Finally, add any extra resolveTroves
        """
        rmakeCfg = super(Builder, self)._getRmakeConfig(rmakeCfgFn)
        if extraResolveTroves is not None:
            rmakeCfg.configKey(
                'resolveTroves',
                ' '.join('%s=%s' % r for r in extraResolveTroves),
                )
        return rmakeCfg

    def build(self, troveSpecs, resolveTroves):
        """Build a list of troves.

        @param troveSpecs: list of trove specs
        @type troveSpecs: [(name, versionObj, flavorObj), ...]
        @param resolveTroves: set of version objects to use for resolveTroves
        @type resolveTroves: set([TroveSpec, ...])
        @return troveMap: dictionary of troveSpecs to built troves
        """

        if not troveSpecs:
            return {}

        rmakeCfg = self._getRmakeConfig(self._rmakeCfgFn, resolveTroves)
        self._helper = self.getRmakeHelper(rmakeCfg)
        return super(Builder, self).build(troveSpecs)

    def getRmakeHelper(self, rmakeCfg):
        return helper.rMakeHelper(buildConfig=rmakeCfg)


class Updater(UpdaterSuperClass):
    """Class for finding and updating packages sourced from artifactory
    """

    def create(self, buildAll=False, recreate=False):
        """Import new packages into the repository

        @param buildAll: build all binary packages, even if the source didn't
            change
        @type buildAll: bool
        @param recreate: recreate source packages even if they already exist
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
        chunk_size = 20
        total = len(self._pkgSource.pkgQueue)

        def addPackage(p, isDeps=False):
            try:
                version = verCache.get(
                    ('%s:source' % p.name, p.getConaryVersion(), None))
                if not version or recreate:
                    log.info(
                        'attempting to import %s (%s/%s)',
                        '/'.join(p.getGAV()),
                        total - len(self._pkgSource.pkgQueue),
                        total,
                        )
                    manifest = dict(
                        version=p.getConaryVersion(),
                        build_requires=p.buildRequires,
                        artifacts=p.artifacts,
                        )
                    self._conaryhelper.setJsonManifest(p.name, manifest)
                    version = self._conaryhelper.commit(
                        p.name, commitMessage=self._cfg.commitMessage)
                else:
                    log.info(
                        'not importing %s (%s/%s)',
                        '/'.join(p.getGAV()),
                        total - len(self._pkgSource.pkgQueue),
                        total,
                        )

                binVersion = verCache.get((p.name, p.getConaryVersion(), None))
                if (not binVersion or binVersion.getSourceVersion() != version
                        or buildAll or recreate):
                    chunk.add(((p.name, version, None), p))
                else:
                    log.info('not building %s=%s' % (p.name, version))

                if binVersion and isDeps:
                    resolveTroves.add((p.name, binVersion))
            except Exception as e:
                fail.add((p, e))

        def getDependencies(pkg):
            deps = set()
            for dep in pkg.dependencies:
                if dep in self._pkgSource.pkgQueue:
                    self._pkgSource.pkgQueue.remove(dep)
                    deps.add(dep)
                    deps.update(getDependencies(dep))
            return deps

        prevLength = None
        loopCount = 0
        while self._pkgSource.pkgQueue:
            pkg = self._pkgSource.pkgQueue.popleft()
            pkgs = getDependencies(pkg)
            pkgs.add(pkg)
            currentPkgNames = [c[0][0] for c in chunk]
            pkgMatch = any(p.name in currentPkgNames for p in pkgs)
            if pkgMatch:
                # send to end of queue
                self._pkgSource.pkgQueue.extend(pkgs)
            else:
                for idx, pkg in enumerate(pkgs):
                    addPackage(pkg, isDeps=bool(idx))

            length = len(self._pkgSource.pkgQueue)
            if length == prevLength:
                loopCount += 1

            if len(chunk) >= chunk_size or loopCount > length:
                toBuild.append((chunk, resolveTroves))
                chunk = set()
                resolveTroves = set()
                loopCount = 0

            prevLength = length

        return toBuild, fail
