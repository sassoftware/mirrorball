#!/usr/bin/python
#
# Copyright (c) 2006,2008 rPath, Inc.
#
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

'''
Module for creating package recipes and managing source components.
'''

import os
import shutil
from conary import cvc

class RecipeMaker(object):
    '''
    Class for creating and managing rpm factory based source components.
    '''

    def __init__(self, cfg, repos, rpmSource):
        self.cfg = cfg
        self.repos = repos
        self.rpmSource = rpmSource

    def _createSourceComponent(self, pkgname, recipeContents=None,
                               manifestContents=None, newPkgArgs={}):
        print 'creating initial template for', pkgname
        try:
            shutil.rmtree(pkgname)
        except OSError, e:
            pass
        cvc.sourceCommand(self.cfg, [ "newpkg", pkgname ], newPkgArgs)
        cwd = os.getcwd()
        os.chdir(pkgname)
        try:
            addfiles = [ 'add' ]
            if recipeContents:
                recipe = pkgname + '.recipe'
                f = open(recipe, 'w')
                f.write(recipeContents)
                f.close()
                addfiles.append(recipe)
            if manifestContents:
                manifest = 'manifest'
                f = open(manifest, 'w')
                f.write(manifestContents)
                f.close()
                addfiles.append(manifest)

            cvc.sourceCommand(self.cfg, addfiles, {'text':True})
            try:
                cvc.sourceCommand(self.cfg, ['cook'], {'no-deps': None})
            except Exception, e:
                print '++++++ error building', pkgname, str(e)
                return
            cvc.sourceCommand(self.cfg,
                             [ 'commit' ],
                             { 'message':
                               'Automated initial commit of %s:source'
                                % pkgname})
            #cvc.sourceCommand(self.cfg, ['cook', pkgname], {'no-deps': None})
            #cfg = copy.copy(self.cfg)
            #buildFlavor = deps.deps.parseFlavor('is:x86_64')
            #cfg.buildFlavor = deps.deps.overrideFlavor(
            #    cfg.buildFlavor, buildFlavor)
            #cvc.sourceCommand(cfg, ['cook', pkgname], {'no-deps': None})
        finally:
            os.chdir(cwd)

    def _updateSourceComponent(self):
        raise NotImplemented

    def _createOrUpdateManifest(self, pkgname, srpm, prefix,
                                create=False, update=False):
        assert(create or update)
        manifest = self.rpmSource.createManifest(srpm, prefix)

        if create:
            fn = self._createSourceComponent
        else:
            fn = self._updateSourceComponent

        fn(pkgname, manifestContents=manifest,
           newPkgArgs={'factory':'sle-rpm'})

    def createManifest(self, pkgname, srpm, prefix):
        self._createOrUpdateManifest(pkgname, srpm, prefix, create=True)

    def updateManifest(self, pkgname, srpm, prefix):
        self._createOrUpdateManifest(pkgname, srpm, prefix, update=True)

    def createRecipe(self, pkgname, recipeContents):
        self._createSourceComponent(pkgname, recipeContents=recipeContents)
