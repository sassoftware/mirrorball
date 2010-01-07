#!/usr/bin/python
#
# Copyright (c) 2009-2010 rPath, Inc.
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
Script for generating group model from current state of the repository.
"""

import os
import sys

sys.path.insert(0, os.environ['HOME'] + '/hg/conary')
sys.path.insert(0, os.environ['HOME'] + '/hg/xobj/py')
sys.path.insert(0, os.environ['HOME'] + '/hg/rbuilder-trunk/rpath-xmllib')

from conary.lib import util
sys.excepthook = util.genExcepthook()

mbdir = os.path.abspath('../')
sys.path.insert(0, mbdir)

confDir = os.path.join(mbdir, 'config', sys.argv[1])

from updatebot import log
from updatebot import Bot
from updatebot import UpdateBotConfig

import time
import logging

slog = logging.getLogger('script')

log.addRootLogger()
cfg = UpdateBotConfig()
cfg.read(os.path.join(confDir, 'updatebotrc'))

bot = Bot(cfg)

from updatebot import groupmgr

mgr = groupmgr.GroupManager(cfg)

slog.info('retrieving trove information')
troves = mgr._helper._getLatestTroves()
label = mgr._helper._ccfg.buildLabel
allTroves = mgr._helper._repos.getTroveLeavesByLabel({None: {label: None}})
mgr._checkout()

import itertools
for k1, k2 in itertools.izip(sorted(troves), sorted(allTroves)):
    assert k1 == k2
    a = troves[k1]
    b = allTroves[k2]
    if not k1.startswith('group-') and len(a.values()[0]) != len(b.values()[0]):
        slog.error('unhandled flavor found %s' % k1)
        raise RuntimeError

#import epdb; epdb.st()

for name, vf in troves.iteritems():
    if ':' in name or bot._updater._fltrPkg(name):
        continue

    versions = vf.keys()
    assert len(versions) == 1
    versions.sort()
    version = versions[-1]
    flavors = vf[version]

    mgr.addPackage(name, version, flavors)

#import epdb; epdb.st()

mgr.setVersion('0')
mgr.setErrataState('0')
mgr._copyVersions()
mgr._validateGroups()
mgr._helper.setModel(mgr._sourceName, mgr._groups)
#mgr._commit()
#mgr.build()

import epdb; epdb.st()
