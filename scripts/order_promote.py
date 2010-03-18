#!/usr/bin/python
#
# Copyright (c) 2010 rPath, Inc.
#
# This program is distributed under the terms of the Common Public License,
# version 1.0. A copy of this license should have been distributed with this
# source file in a file called LICENSE. If it is not present, the license
# is always available at http://www.rpath.com/permanent/licenses/CPL-1.0.
#
# This program is distributed in the hope that it will be useful, but
# without any warranty; without even the implied warranty of merchantability
# or fitness for a particular purpose. See the Common Public License for
#

"""
Script for promoting groups in the correct order.
"""

import os
import sys
import itertools

sys.path.insert(0, os.environ['HOME'] + '/hg/conary')
sys.path.insert(0, os.environ['HOME'] + '/hg/xobj/py')
sys.path.insert(0, os.environ['HOME'] + '/hg/rbuilder-trunk/rpath-xmllib')

from conary.lib import util
sys.excepthook = util.genExcepthook()

from conary import versions
from conary.conaryclient import cmdline

mbdir = os.path.abspath('../')
sys.path.insert(0, mbdir)

confDir = os.path.join(mbdir, 'config', sys.argv[1])

import rhnmirror

from updatebot import log
from updatebot import conaryhelper
from updatebot import OrderedBot
from updatebot import UpdateBotConfig
from updatebot.lib.watchdog import forknwait

slog = log.addRootLogger()
cfg = UpdateBotConfig()
cfg.read(os.path.join(confDir, 'updatebotrc'))

mcfg = rhnmirror.MirrorConfig()
mcfg.read(confDir + '/erratarc')

errata = rhnmirror.Errata(mcfg)
errata.fetch()

bot = OrderedBot(cfg, errata)
bot._pkgSource.load()

helper = conaryhelper.ConaryHelper(cfg)

def getUpstreamVersionMap(groupvers):
    # Turn groupvers into something we can work with.
    grpVerMap = {}
    for n, v, f in groupvers:
        upver = v.trailingRevision().getVersion()
        grpVerMap.setdefault(upver, dict()).setdefault(v, set()).add((n, v, f))

    # Find the latest conary versions of all upstream versions
    latestMap = {}
    for upver, vers in grpVerMap.iteritems():
        latest = None
        for v, nvfs in vers.iteritems():
            if latest is None:
                latest = v
                continue
            if latest < v:
                latest = v

        # Store the latest versions that we need to promote
        assert upver not in latestMap
        latestMap[upver] = vers[latest]
    return latestMap

def updateLatestMap():
    # Get all of the binary versions of the top level group
    slog.info('querying repository for all group versions')
    groupvers = helper.findTrove(cfg.topGroup, getLeaves=False)
    latestMap = getUpstreamVersionMap(groupvers)
    return latestMap

latestMap = updateLatestMap()

# Get all target versions
slog.info('querying target label for all group versions')
targetGroupvers = helper.findTrove((cfg.topGroup[0], cfg.targetLabel, None), getLeaves=False)
targetLatest = getUpstreamVersionMap(targetGroupvers)

searchPath = [ x for x in itertools.chain((helper._ccfg.buildLabel, ), cfg.platformSearchPath) ]

# Get all updates after the first bucket.
missing = False
for updateId, bucket in bot._errata.iterByIssueDate(current=1):
    upver = bot._errata.getBucketVersion(updateId)

    if upver in targetLatest:
        slog.info('%s found on target label, skipping' % upver)
        continue

    # make sure version has been imported
    if upver not in latestMap:
        missing = upver
        continue

    slog.info('starting promote of %s' % upver)

    # If we find a missing version and then find a version in the
    # repository report an error.
    if missing:
        slog.critical('found missing version %s' % missing)
        raise RuntimeError

    # Get conary versions to promote
    topGroups = latestMap[upver]
    toPromote = []
    for n, v, f in topGroups:
        toPromote.append((n, v, f))
        toPromote.append(('group-rhel-packages', v, f))
        toPromote.append(('group-rhel-standard', v, f))

    # Make sure we have the expected number of flavors
    if len(topGroups) != len(cfg.groupFlavors):
        slog.error('did not find expected number of flavors')
        raise RuntimeError

    # Find expected promote packages.
    csrcTrvs = [ ('%s:source' % x.name, x.getConaryVersion(), None)
                 for x in bucket ]
    srcTrvs = helper.findTroves(csrcTrvs, labels=searchPath)

    # Map source versions to binary versions.
    slog.info('retrieving binary trove map')
    srcTrvMap = helper.getBinaryVersions([ (x, y, None) for x, y, z in
                                       itertools.chain(*srcTrvs.itervalues()) ],
                                       labels=searchPath)

    # These are the binary trove specs that we expect to be promoted.
    expected = [ x for x in itertools.chain(*srcTrvMap.itervalues()) ]

    # Get list of extra troves from the config
    extra = cfg.extraExpectedPromoteTroves.get(updateId, [])

    @forknwait
    def promote():
        # Create and validate promote changeset
        packageList = helper.promote(toPromote, expected, cfg.sourceLabel,
                                     cfg.targetLabel, commit=True,
                                     extraExpectedPromoteTroves=extra)
        return 1

    rc = promote()

    # Update latest map for the next loop
    latestMap = updateLatestMap()

    versions.clearVersionCache()

import epdb; epdb.st()
