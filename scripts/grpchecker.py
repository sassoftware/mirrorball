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
Script for finding and fixing group issues.
"""

import os
import sys

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

sourceVersion = None
if len(sys.argv) == 3:
    sourceVersion = cmdline.parseTroveSpec(sys.argv[2])[1]

from updatebot import log
from updatebot import groupmgr
from updatebot import conaryhelper
from updatebot import UpdateBotConfig

from updatebot.errors import OldVersionsFoundError
from updatebot.errors import GroupValidationFailedError
from updatebot.errors import NameVersionConflictsFoundError
from updatebot.errors import ExpectedRemovalValidationFailedError

import time
import logging

slog = log.addRootLogger()
cfg = UpdateBotConfig()
cfg.read(os.path.join(confDir, 'updatebotrc'))

mgr = groupmgr.GroupManager(cfg)
helper = conaryhelper.ConaryHelper(cfg)

def handleVersionConflicts(group, error):
    conflicts = error.conflicts
    binPkgs = error.binPkgs

    toAdd = {}
    toRemove = set()
    for source, svers in conflicts.iteritems():
        assert len(svers) == 2
        svers.sort()
        old = binPkgs[(source, svers[0], None)]
        new = binPkgs[(source, svers[1], None)]

        toRemove.update(set([ x[0] for x in old ]))

        for n, v, f, in new:
            if n in toRemove:
                toAdd.setdefault((n, v), set()).add(f)

    return toRemove, toAdd

def handleVersionErrors(group, error):
    toAdd = {}
    toRemove = set()
    for pkgName, (modelContents, repoContents) in error.errors.iteritems():
        toRemove.update(set([ x[0] for x in modelContents ]))

        for n, v, f in repoContents:
            if n in toRemove:
                toAdd.setdefault((n, v), set()).add(f)

    return toRemove, toAdd

def handleRemovalErrors(group, error):
    toAdd = {}
    toRemove = set(error.pkgNames)

    return toRemove, toAdd

def checkVersion(ver):
    mgr._sourceVersion = ver
    mgr._checkout()
    mgr._copyVersions()

    changes = []

    try:
        mgr._validateGroups()
    except GroupValidationFailedError, e:
        for group, error in e.errors:
            if isinstance(error, NameVersionConflictsFoundError):
                changes.append(handleVersionConflicts(group, error))
            elif isinstance(error, OldVersionsFoundError):
                changes.append(handleVersionErrors(group, error))
            elif isinstance(error, ExpectedRemovalValidationFailedError):
                changes.append(handleRemovalErrors(group, error))
            else:
                raise error

    return ver, changes

srcName, srcVersion, srcFlavor = cfg.topSourceGroup
troves = helper.findTrove(('%s:source' % srcName, srcVersion, srcFlavor), getLeaves=False)

troveSpec = ('%s:source' % cfg.topSourceGroup[0], sourceVersion, None)
sourceVersion = helper.findTroves((troveSpec, )).values()[0][0][1]

nv = []
start = False
for n, v, f in sorted(troves):
    if sourceVersion and v == sourceVersion:
        start = True
    if not start:
        continue
    nsv = (n, v.getSourceVersion())
    if nsv not in nv:
        nv.append(nsv)

if not start:
    raise RuntimeError

toUpdate = []
for n, v in nv:
    ver, changed = checkVersion(v)
    # Make sure to only rebuild groups that have changed
    # and every group after.
    if not changed and not toUpdate:
        continue
    toUpdate.append((ver, changed))

#slog.critical('Before going any further, be aware that this will only rebuild '
#    'the groups that need to change, not any other existing groups, if you '
#    'want to maintain order on the devel label you will need to write that '
#    'code.')
#assert False

import epdb; epdb.st()

jobIds = []
removed = {}
for ver, changed in toUpdate:
    mgr._sourceVersion = ver
    mgr._checkout()

    slog.info('updating %s' % ver)

    # Find all names and versions in the group model
    nv = dict([ (y.name, versions.ThawVersion(y.version))
                for x, y in mgr._groups[mgr._pkgGroupName].iteritems() ])

    # Set of packages that should be removed
    removals = set([ x for x, y in removed.iteritems() if nv[x] == y ])

    # Remove old removals
    for pkg in removals:
        slog.info('removing %s' % pkg)
        mgr.remove(pkg)

    for toRemove, toAdd in changed:
        # Handle removes
        for pkg in toRemove:
            slog.info('removing %s' % pkg)
            mgr.remove(pkg)

            # cache removals
            removed[pkg] = nv[pkg]

        # Handle adds
        for (n, v), flvs in toAdd.iteritems():
            slog.info('adding %s=%s' % (n, v))
            mgr.addPackage(n, v, flvs)

    mgr._copyVersions()
    mgr._validateGroups()
    version = mgr.save(copyToLatest=True)
    jobId = mgr._builder.start(((mgr._sourceName, version, None), ))
    jobIds.append(jobId)

for jobId in jobIds:
    mgr._builder.watch(jobId)

#import epdb; epdb.st()

for jobId in jobIds:
    mgr._builder.commit(jobId)

import epdb; epdb.st()
