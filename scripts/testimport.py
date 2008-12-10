#!/usr/bin/python2.6
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

import os
import sys

sys.path.insert(0, os.environ['HOME'] + '/hg/26/rpath-xmllib')
sys.path.insert(0, os.environ['HOME'] + '/hg/26/conary')
sys.path.insert(0, os.environ['HOME'] + '/hg/26/mirrorball')
sys.path.insert(0, os.environ['HOME'] + '/hg/26/epdb')
sys.path.insert(0, os.environ['HOME'] + '/hg/26/rmake')

from conary.lib import util
sys.excethook = util.genExcepthook()

from updatebot import log
from updatebot import config
from updatebot import conaryhelper

from conary.deps import deps
from conary.build import use
from conary.build import lookaside
from conary.build import loadrecipe

log.addRootLogger()
cfg = config.UpdateBotConfig()
cfg.read(os.environ['HOME'] + '/hg/26/mirrorball/config/%s/updatebotrc' % sys.argv[1])

import logging
slog = logging.getLogger('script')

rpmOld = sys.argv[2]
rpmNew = sys.argv[3]

helper = conaryhelper.ConaryHelper(cfg)
ccfg = helper._ccfg
repos = helper._repos

lcache = lookaside.RepositoryCache(repos)

def filterSrcTrvs(trvLst):
    return [ x for x in trvLst if
        not x[0].startswith('info-') and
        not x[0].startswith('group-') and
        not x[0].startswith('factory-') and
        not x[0].split(':')[0] in cfg.excludePackages ]

def getManifest(trvSpec):
    return helper.getManifest(trvSpec[0].split(':')[0])

def getRcpObj(fn, manifest, srcTrove):
    kwargs = {
        'cfg': ccfg,
        'repos': repos,
        'loadAutoRecipes': False
    }

    rcpClass = loadrecipe.RecipeLoaderFromString(open(fn).read(), fn, **kwargs).getRecipe()
    rcpClass._trove = srcTrove

    srcdirs = [ ccfg.sourceSearchDir % {'pkgname': rcpClass.name} ]
    classArgs = (ccfg, lcache, srcdirs)
    classKwargs = {'lightInstance': True}

    rcpObj = rcpClass(*classArgs, **classKwargs)
    rcpObj.name = srcTrove.getName().split(':')[0]
    rcpObj.version = srcTrove.getVersion().trailingRevision().getVersion()
#    rcpObj.rpmUrl = ccfg.macros['repositoryUrl']
    rcpObj.rpms = manifest
    rcpObj.sourceFiles = manifest
    rcpObj.importScripts = False

    rcpObj.populateLcache()
    rcpObj.loadPolicy()
    rcpObj.setup()

    return rcpObj

def dedupFiles(fileLst):
    map = {}
    for f in fileLst:
        map[(f.sourcename, f.use)] = f
    return map.values()

def testOneSLES((name, version, flavor), bldflv, expected):
    # setup use flags for one flavor
    use.setBuildFlagsFromFlavor(name, bldflv, error=False)

    manifest = getManifest((name, version, flavor))
    srcTrove = repos.getTrove(name, version, deps.Flavor())

    rcpOldObj = getRcpObj(rpmOld, manifest, srcTrove)
    rcpNewObj = getRcpObj(rpmNew, manifest, srcTrove)

    oldFiles = rcpOldObj.getSourcePathList()
    newFiles = rcpNewObj.getSourcePathList()

    if not len(oldFiles) == len(newFiles):
        if name in ('glibc:source', 'db:source'):
            import epdb; epdb.st()
            oldFiles = dedupFiles(oldFiles)
            newFiles = dedupFiles(newFiles)
            if len(oldFiles) != len(newFiles):
                import epdb; epdb.st()
        else:
            import epdb; epdb.st()

    pkgs = set()
    for i in range(len(oldFiles)):
        oldFile = oldFiles[i]
        newFile = newFiles[i]

        assert oldFile.sourcename == newFile.sourcename
        assert oldFile.use == newFile.use
        assert oldFile.package == newFile.package

        if oldFile.package is not None:
            pkgs.add(oldFile.package)

    if expected.difference(pkgs):
        if name != 'gcc:source':
            import epdb; epdb.st()

def testOneCentOS((name, version, flavor), bldflv, expected):
    use.setBuildFlagsFromFlavor(name, bldflv, error=False)

    manifest = getManifest((name, version, flavor))
    srcTrove = repos.getTrove(name, version, deps.Flavor())

    rcpNewObj = getRcpObj(rpmNew, manifest, srcTrove)
    newFiles = rcpNewObj.getSourcePathList()

    pkgs = set([ x.package for x in newFiles if x is not None ])

    if expected.difference(pkgs):
        if name not in ('vim:source', 'compat-gcc-32:source', 'gcc:source', 'MAKEDEV:source', 'python:source', ):
            import epdb; epdb.st()

if sys.argv[1] == 'sles':
    compareOne = testOneSLES
elif sys.argv[1] == 'centos':
    compareOne = testOneCentOS

def doOne(trv, srcTrvMap):
    expected = set([ x[0].split(':')[0] for x in srcTrvMap[trv] ])
    slog.info('checking %s=%s' % (trv[0], trv[1]))
    compareOne(trv, ccfg.buildFlavor, expected)



ccfg.setContext('x86')
srcTrvMap = helper.getSourceTroves(cfg.topGroup)
srcTrvs = filterSrcTrvs(srcTrvMap.keys())

start = 'gawk:source'
started = False
skipLst = ('kernel:source', )

for trv in srcTrvs:
    if trv[0] == start:
        started = True
    if not started or trv[0] in skipLst:
        slog.info('skipping %s' % trv[0])
        continue
    doOne(trv, srcTrvMap)

slog.info('done')
import epdb; epdb.st()
