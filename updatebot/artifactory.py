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

from . import cmdline
from . import pkgsource
from .bot import Bot as BotSuperClass
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
        #self._builder = build.Builder(self._cfg, self._ui)

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

        for chunk in buildSet:
            toBuild = self._formatBuildTroves(chunk)
            if len(toBuild):
                log.info('found %s packages to build' % len(toBuild))

                # Build all newly imported packages.
                failed = self._builder.build(toBuild)
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


class Updater(UpdaterSuperClass):
    """Class for finding and updating packages sourced from artifactory
    """

    def create(self, buildAll=False, recreate=False):
        """Import new packages into the repository
        """
        troveList = []
        for p in self._pkgSource.pkgQueue:
            troveList.append((p.name, p.getConaryVersion(), None))
            troveList.append(('%s:source' % p.name, p.getConaryVersion(), None))

        verCache = {}
        for k, v in self._conaryhelper.findTroves(
                troveList, allowMissing=True).iteritems():
            if len(v) > 1:
                import epdb; epdb.st()  # XXX breakpoint
            verCache[k] = v[0][1]  # v is a list of a tuple (name, ver, flav)

        fail = set()
        chunk = set()
        toBuild = []
        chunk_size = 10
        total = len(self._pkgSource.pkgQueue)

        def addPackage(p):
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
                    version = self._conaryhelper.commit(p.name,
                        commitMessage=self._cfg.commitMessage)

                binVersion = verCache.get((p.name, p.getConaryVersion(), None))
                if (not binVersion or binVersion.getSourceVersion() != version
                        or buildAll or recreate):
                    chunk.add(((p.name, version, None), p))
            except Exception as e:
                log.error('failed to import %s: %s', '/'.join(p.getGAV()), e)
                import epdb; epdb.st()  # XXX breakpoint
                fail.add((p, e))

        def addDependencies(p):
            for gav in p.dependencies:
                dep = self._pkgSource.pkgMap[gav]
                if dep in self._pkgSource.pkgQueue:
                    self._pkgSource.pkgQueue.remove(dep)
                addPackage(dep)
                addDependencies(dep)

        while self._pkgSource.pkgQueue:
            if len(chunk) >= chunk_size:
                toBuild.append(chunk)
                chunk = set()
            pkg = self._pkgSource.pkgQueue.pop()
            addPackage(pkg)
            addDependencies(pkg)

        return toBuild, fail
