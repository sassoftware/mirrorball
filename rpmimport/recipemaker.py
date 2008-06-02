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

"""
Module for creating factory manifest and managing source components
"""

import os
import shutil
from conary import cvc

class RecipeMaker(object):
    """
    Class for creating and managing rpm factory based source components.
    """

    def __init__(self, cfg, repos, rpmSource):
        self.cfg = cfg
        self.repos = repos
        self.rpmSource = rpmSource

    def _updateSourceComponent(self, pkgname, manifestContents,
                               comment):
        """
        Update the manifest file in the current working directory,
        preform a test cook, and commit
        Assumptions: current working directory is a checkout
        """
        f = open('manifest', 'w')
        f.write(manifestContents)
        f.close()
        try:
            cvc.sourceCommand(self.cfg, ['cook'], {'no-deps': None})
        except Exception, e:
            print '++++++ error building', pkgname, str(e)
            return
        return
        cvc.sourceCommand(self.cfg,
                         [ 'commit' ],
                         { 'message':
                           '%s of %s:source' % (comment, pkgname)})

    def _newpkg(self, pkgname):
        """
        Run the "cvc newpkg" related tasks when creating a new :source
        component.
        Assumption: current working directory is where the new checkout
                    should be created
        Side effect: current working directory will be the checkout
                     directory when this method returns
        """
        print 'creating initial template for', pkgname
        try:
            shutil.rmtree(pkgname)
        except OSError, e:
            pass
        cvc.sourceCommand(self.cfg, [ "newpkg", pkgname ],
                          {'factory':'sle-rpm'})
        os.chdir(pkgname)
        f = open(manifest, 'w')
        f.close()
        addfiles.append(manifest)
        cvc.sourceCommand(self.cfg, addfiles, {'text':True})

    def _checkout(self, pkgname):
        """
        Check out an existing :source component
        Assumption: current working directory is where the new checkout
                    should be created
        Side effect: current working directory will be the checkout
                     directory when this method returns
        """
        print 'updating', pkgname
        try:
            shutil.rmtree(pkgname)
        except OSError, e:
            pass
        cvc.sourceCommand(self.cfg, [ 'co', pkgname ], {})
        os.chdir(pkgname)

    def _createOrUpdate(self, pkgname, srpm, create=False, update=False):
        assert(create or update)
        manifest = self.rpmSource.createManifest(srpm)

        cwd = os.getcwd()
        try:
            if create:
                self._newpkg(pkgname)
                comment = 'Automated initial commit'
            else:
                self._checkout(pkgname)
                comment = 'Automated update'
            self._updateSourceComponent(pkgname, manifest, comment)
        finally:
            os.chdir(cwd)

    def createManifest(self, pkgname, srpm):
        self._createOrUpdate(pkgname, srpm, create=True)

    def updateManifest(self, pkgname, srpm):
        self._createOrUpdate(pkgname, srpm, update=True)
