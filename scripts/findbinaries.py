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
sys.path.insert(0, os.environ['HOME'] + '/hg/26/xobj/py')
sys.path.insert(0, os.environ['HOME'] + '/hg/26/rmake')

from conary.lib import util
sys.excepthook = util.genExcepthook()

import copy
import logging

from updatebot import log
from updatebot import bot
from updatebot import errors
from updatebot import config
from updatebot import conaryhelper

log.addRootLogger()

slog = logging.getLogger('findbinaries')

cfg = config.UpdateBotConfig()
cfg.read(os.environ['HOME'] + '/hg/26/mirrorball/config/sles/updatebotrc')

bot = bot.Bot(cfg)
updater = bot._updater
helper = updater._conaryhelper

def filterPkgs(collection):
    def fltr(name):
        if type(name) == tuple:
            name = name[0]

        if (name.split(':')[0] in cfg.excludePackages or
            name.startswith('info-') or
            name.startswith('factory-') or
            name.startswith('group-')):
            return True
        return False

    newCollection = copy.deepcopy(collection)
    for item in collection:
        if not fltr(item):
            continue
        if type(collection) == dict:
            del newCollection[item]
        else:
            newCollection.remove(item)

    return newCollection


pkgs = helper._repos.getTroveLeavesByLabel({None: {helper._ccfg.buildLabel: None}})
groupPkgs = helper.getSourceTroves(cfg.topGroup)

pkgs = filterPkgs(pkgs)
groupPkgs = filterPkgs(groupPkgs)

pkgSet = set([ x.split(':')[0] for x in pkgs ])

# remove versions and flavors from groupPkgs
grpPkgs = {}
for key, value in groupPkgs.iteritems():
    key = key[0].split(':')[0]
    if key not in grpPkgs:
        grpPkgs[key] = set()

    for item in value:
        grpPkgs[key].add(item[0])

# Build of map of the latest versions of all src:set([binary, ...]) that are
# on the buildLabel.
srcDict = {}
for pkg in pkgSet:
    # This is normally due to unbuilt sources.
    if pkg not in pkgs:
        slog.warn('skipping %s' % pkg)
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
        if src not in srcDict:
            srcDict[src] = set()

        for bin in binSet:
            name = bin[0].split(':')[0]
            srcDict[src].add((name, bin[1], bin[2]))

srcNameDict = {}
for src, binSet in srcDict.iteritems():
    latest = None
    for bin in binSet:
        if not latest:
            latest = bin[1]

        if bin[1] > latest:
            latest = bin[1]

    if src[0] not in srcNameDict:
        srcNameDict[src[0]] = set()

    for bin in binSet:
        if bin[1] == latest:
            srcNameDict[src[0]].add(bin[0])


# Now that we have a mapping of source trove name to set of binary trove names
# find the sources and binaries that are not included in the group.
newPkgs = {}
for srcName in srcNameDict:
    if srcName not in grpPkgs:
        newPkgs[srcName] = srcNameDict[srcName]
    else:
        newPkgs[srcName] = srcNameDict[srcName].difference(grpPkgs[srcName])

# Flatten the newPkgs dict to a list of binaries
bins = set()
for value in newPkgs.itervalues():
    bins.update(value)

binLst = list(bins)
binLst.sort()

for item in binLst:
    print ' ' * 11, '\'%s\',' % item
