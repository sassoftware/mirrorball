#!/usr/bin/python
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

sys.path.insert(0, os.environ['HOME'] + '/hg/rpath-xmllib')
sys.path.insert(0, os.environ['HOME'] + '/hg/conary')
sys.path.insert(0, os.environ['HOME'] + '/hg/mirrorball')

import logging

from updatebot import log
from updatebot import bot
from updatebot import config
from updatebot import conaryhelper

log.addRootLogger()

slog = logging.getLogger('findbinaries')

cfg = config.UpdateBotConfig()
cfg.read(os.environ['HOME'] + '/hg/mirrorball/config/centos/updatebotrc')

bot = bot.Bot(cfg)
bot._populatePkgSource()

updater = bot._updater
helper = updater._conaryhelper

sources, failed = updater.create(cfg.package, buildAll=True)

pkgs = helper._repos.getTroveLeavesByLabel({None: {helper._ccfg.buildLabel: None}})
pkgSet = set([ x.split(':')[0] for x in pkgs ])

#import epdb; epdb.st()

srcDict = {}
for pkg in pkgSet:
    if pkg not in pkgs:
        slog.warn('skipping %s, not in packages' % pkg)
        continue
    version = pkgs[pkg].keys()[0]
    flavors = pkgs[pkg][version]
    if len(flavors) == 0:
        flavor = None
    else:
        flavor = flavors[0]

    slog.info('getting binaries for %s' % pkg)
    for src, binSet in helper._getSourceTroves((pkg, version, flavor)).iteritems():
        src = (src[0].split(':')[0], src[1], src[2])
        if src not in sources:
            slog.warn('skipping %s, it not in sources' % src[0])
            continue

        if src not in srcDict:
            srcDict[src] = set()

        for bin in binSet:
            name = bin[0].split(':')[0]
            srcDict[src].add((name, bin[1], bin[2]))

bins = set()
for src, binSet in srcDict.iteritems():
    latest = None
    for bin in binSet:
        if not latest:
            latest = bin[1]

        if bin[1] > latest:
            latest = bin[1]

    for bin in binSet:
        if bin[1] == latest:
            bins.add(bin[0])

binLst = list(bins)
binLst.sort()

for item in binLst:
    print ' ' * 11, '\'%s\',' % item
