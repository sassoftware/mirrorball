#!/usr/bin/python
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
import sys
import time

mirrorballDir = os.path.abspath('../')
sys.path.insert(0, mirrorballDir)

from conary.lib import cfg
import os
import requests
import json
from urlparse import urljoin

from conary.lib import util
sys.excepthook = util.genExcepthook()

from updatebot import bot
from updatebot import config
from updatebot import log
from updatebot import conaryhelper
from conary.lib import util
from updatebot.errors import NoManifestFoundError



class Helper(conaryhelper.ConaryHelper):
    def __init__(self, cfg):
        conaryhelper.ConaryHelper.__init__(self, cfg)

    def getManifestCfg(self, pkgname, manifest, version=None):
        """
        Get the manifest file from the source component for a
        given package.
        @param pkgname: name of the package to retrieve
        @type pkgname: string
        @param version optional source version to checkout.
        @type version conary.versions.Version
        @return manifest for pkgname
        """

        print('retrieving manifest for %s' % pkgname)
        recipeDir = self._edit(pkgname, version=version)
        manifestFileName = util.joinPaths(recipeDir, 'manifest')

        if not os.path.exists(manifestFileName):
            raise NoManifestFoundError(pkgname=pkgname, dir=recipeDir)

        manifest.read(manifestFileName)

        return manifest

    def setManifestCfg(self, pkgname, manifest, version=None):
        """
        Create/Update a manifest file from config.
        @param pkgname: name of the package
        @type pkgname: string
        @param manifest: list of files to go in the manifest file
        @type manifest: list(string, string, ...)
        """

        print('setting manifest for %s' % pkgname)
        recipeDir = self._edit(pkgname, version=version)
        # Update manifest file.
        manifestFileName = util.joinPaths(recipeDir, 'manifest')
        manifest.writeToFile(manifestFileName)
        # Make sure manifest file has been added.
        self._addFile(recipeDir, 'manifest')


    

class GemManifest(cfg.ConfigFile):
    name = cfg.CfgString
    version = cfg.CfgString
    gem_uri = cfg.CfgString
    api = (cfg.CfgString, 'https://rubygems.org/api/v1/gems/')
    build_requires = cfg.CfgLineList(cfg.CfgString)
    environment = cfg.CfgDict(cfg.CfgString)
    require_exceptions = cfg.CfgQuotedLineList(cfg.CfgString)


class GemInfo(object):
    def __init__(self, gemname, api=None):
        self.name = gemname
        self.api = api or 'https://rubygems.org/api/v1/gems/'
        self.uri = urljoin(self.api,self.name)

    def jsonToInfo(self, str):
        def j2o(load):
            if isinstance(load, dict):
                return type('info', (), dict([(k,j2o(v)) for k,v in load.iteritems()]) )
            else:
                if isinstance(load, unicode):
                    return load.encode()
                return load
        return j2o(json.loads(str))

    def getInformation(self):
        r = requests.get(self.uri)
        if not r.ok:
            raise
        return self.jsonToInfo(r.text)



class GemUpdater(object):
    def __init__(self, gemname, info, ccfg, pkgname=None, version=None, prefix=None):
        self.name = gemname
        self.pkgname = pkgname or gemname
        self.info = info
        self.helper = Helper(ccfg)
        self.helper._newPkgFactory = ccfg.gemPackageFactory
        self.version = version
        if not self.version:
            self.version = self.info.version
        self.prefix = prefix
        if not self.prefix:
            self.prefix = ''
        self.msg = "Gem Updater Auto Commit" 

    def getManifest(self, mcfg, version=None):
        return self.helper.getManifestCfg(self.pkgname, mcfg, version)

    def setManifest(self, mcfg, version=None):
        return self.helper.setManifestCfg(self.pkgname, mcfg, version)

    def readManifest(self):
        manifest = GemManifest()
        return self.getManifest(manifest)

    def _newRequires(self, requires=[]):
        requires = [ x['name'].encode() for x in self.info.dependencies.runtime
                            if x not in requires ]
        reqmap = [ (self.prefix + x, None, None) for x in requires ]

        reqtroves = self.helper.findTroves(reqmap)
        #import epdb;epdb.st()
        reqs = [ x[0] for x in reqtroves ]
        missing = [ x for x in reqs if x[0].replace(self.prefix, '') not in requires ]
        if missing:
            print "Missing reqs : %s" % missing
        return reqs  

    def check(self, manifest, info):
        flag = False

        #  FIXME Just in case we passed in a version...
        if not self.version:
            self.version = info.version
 
        if manifest.name != self.name:
            print "[ERROR] Names do not match!!!"
            raise

        if manifest.gem_uri != info.gem_uri:
            print "[WARN] gem_uri do not match!"
            flag = True

        if manifest.version > self.version:
            print "[WARN] version goes backwards"
            flag = True

        if manifest.version < self.version:
            print "[WARN] found newer version : %s " % self.version
            flag = True

        if self._newRequires(manifest.build_requires):
            print "[WARN] New build requires found!"
            flag = True

        return flag

    def _update(self, manifest):
        requires = self._newRequires(manifest.build_requires)
        #  FIXME Just in case we passed in a version...
        manifest.gem_uri = self.info.gem_uri
        # TODO should look up components before adding
        # should flag missing build requires so 
        # we can delay building
        #import epdb;epdb.st()
        # Skipping for now
        #manifest.build_requires.extend(requires)
        manifest.version = self.version
        return manifest

    def _commit(self, manifest, version=None):
        self.setManifest(manifest, version)
        if version:
            self.helper.setVersion(self.pkgname, version)
        return self.helper.commit(self.pkgname, version, self.msg)

    def create(self):
        manifest = GemManifest()
        manifest.name = self.name
        manifest = self._update(manifest)
        return self._commit(manifest)

    def update(self):
        manifest = self.readManifest()
        manifest = self._update(manifest)
        return self._commit(manifest, self.version)



logfile = '%s_%s.log' % (sys.argv[0], time.strftime('%Y-%m-%d_%H%M%S'))

log.addRootLogger(logfile)

_cfg = config.UpdateBotConfig()
_cfg.read(mirrorballDir + '/config/%s/updatebotrc' % sys.argv[1])
obj = bot.Bot(_cfg)
helper = conaryhelper.ConaryHelper(_cfg)

toBuild = []

gemNames = _cfg.gemPackage

prefix = _cfg.gemPrefix

recreate = _cfg.recreate

# Update all of the unique sources.
fail = set()
toBuild = set()
preBuiltPackages = set()
total = len(gemNames)
current = 1

verCache = helper.getLatestVersions()

for gemName in gemNames:
    pkgName = prefix + gemName
    info = GemInfo(gemName).getInformation()
    try:
        # Only import packages that haven't been imported before
        version = verCache.get('%s:source' % pkgName)
        if not version or recreate:
            print('attempting to import %s (%s/%s)'
                     % (pkgName, current, total))
            print "IMPORTING!!! %s" % pkgName
            gu = GemUpdater(gemName, info, _cfg, pkgName)
            version = gu.create()

        if version.trailingRevision().version != info.version:
            print "UPDATING!!! %s" % pkgName
            gu = GemUpdater(gemName, info,  _cfg, pkgName)
            version = gu.update()

        if (not verCache.get(pkgName) or
            verCache.get(pkgName).getSourceVersion() != version
            or recreate):
            toBuild.add((pkgName, version, None))
        else:
            print('not building %s' % pkgName)
            preBuiltPackages.add((pkgName, version, None))
    except Exception, e:
        print('failed to import %s: %s' % (pkgName, e))
        fail.add((pkgName, e))
    current += 1



if toBuild:
    from updatebot import build
    from updatebot.cmdline import display
    from updatebot.cmdline import UserInterface

    ui = UserInterface()

    builder = build.Builder(_cfg, ui, rmakeCfgFn='rmakerc')

    TrvMap = builder.build(toBuild)

    if TrvMap:
        print 'Built the following troves:'
        print display.displayTroveMap(TrvMap)

