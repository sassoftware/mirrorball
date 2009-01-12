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
import logging

sys.path.insert(0, os.environ['HOME'] + '/hg/26/xobj/py')
sys.path.insert(0, os.environ['HOME'] + '/hg/26/mirrorball')

from conary.lib import util
sys.excepthook = util.genExcepthook()

from updatebot import bot
from updatebot.lib import util
from updatebot import config
from updatebot import log as logger

logger.addRootLogger()

log = logging.getLogger('verifymanifest')

cfg = config.UpdateBotConfig()
cfg.read(os.environ['HOME'] + '/hg/26/mirrorball/config/ubuntu/updatebotrc')
b = bot.Bot(cfg)

b._pkgSource.load()

helper = b._updater._conaryhelper

pkgs = []
for n, v, f in helper.getSourceTroves(cfg.topGroup):
    n = n.split(':')[0]
    if len(v.versions) < 3 and v.trailingLabel().asString() == cfg.topGroup[1]:
        if (not n.startswith('group-') and
            not n.startswith('info-') and
            not n.startswith('factory-') and
            not n in cfg.excludePackages):
            v = helper.getLatestSourceVersion(n)
            pkgs.append((n, v.getSourceVersion()))

changed = {}
for i, (pkg, v) in enumerate(pkgs):
    srpms = list(b._pkgSource.srcNameMap[pkg])

    map = {}
    for x in srpms:
        key = '%s_%s' % (x.version, x.release)
        map[key] = x

    key = v.trailingRevision().asString().split('-')[0]
    if key not in map:
        log.info('%s (%s) version not found, using latest' % (pkg, key))
        srcPkg = b._updater._getLatestSource(pkg)
        changed[pkg] = srcPkg
        continue

    changed[pkg] = map[key]


#import epdb; epdb.st()
toBuild = set()
for pkg in changed:
    srcPkg = changed[pkg]
    manifest = b._updater._getManifestFromPkgSource(srcPkg)
    helper.setManifest(pkg, manifest)
    metadata = b._updater._getMetadataFromPkgSource(srcPkg)
    helper.setMetadata(pkg, metadata)

    new = helper.getMetadata(pkg)
    assert metadata == new

    newManifest = helper.getManifest(pkg)
    assert manifest == newManifest

    helper.commit(pkg, commitMessage=cfg.commitMessage)
    toBuild.add((pkg, cfg.topSourceGroup[1], None))

import epdb; epdb.st()

trvMap = b._builder.buildmany(toBuild)

def displayTrove(nvf):
    flavor = ''
    if nvf[2] is not None:
        flavor = '[%s]' % nvf[2]

    return '%s=%s%s' % (nvf[0], nvf[1], flavor)

def display(trvMap):
    for srcTrv in trvMap.iterkeys():
        print displayTrove(srcTrv)
        for binTrv in trvMap[srcTrv]:
            print " " * 4, displayTrove(binTrv)

display(trvMap)

import epdb; epdb.st()
