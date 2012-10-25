#!/usr/bin/python
#
# Copyright (c) rPath, Inc.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#


"""
Script for generating group model from current state of the repository.
"""

import os
import sys

#sys.path.insert(0, os.environ['HOME'] + '/hg/conary')
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
from updatebot import cmdline

import time
import logging

slog = logging.getLogger('script')

log.addRootLogger()
cfg = UpdateBotConfig()
cfg.read(os.path.join(confDir, 'updatebotrc'))

bot = Bot(cfg)

from updatebot import groupmgr
ui = cmdline.UserInterface()

mgr = groupmgr.GroupManager(cfg, ui)

slog.info('retrieving trove information')
troves = mgr._helper._getLatestTroves()
label = mgr._helper._ccfg.buildLabel
allTroves = mgr._helper._repos.getTroveLeavesByLabel({None: {label: None}})
group = mgr.getGroup()

import itertools
for k1, k2 in itertools.izip(sorted(troves), sorted(allTroves)):
    assert k1 == k2
    a = troves[k1]
    b = allTroves[k2]
    if not k1.startswith('group-') and len(a.values()[0]) != len(b.values()[0]):
        slog.error('unhandled flavor found %s' % k1)
        raise RuntimeError

for name, vf in troves.iteritems():
    if ':' in name or bot._updater._fltrPkg(name):
        continue

    versions = vf.keys()
    assert len(versions) == 1
    versions.sort()
    version = versions[-1]
    flavors = vf[version]

    group.addPackage(name, version, flavors)

# Set the errata state and version to some defaults.
group.errataState = 0
group.version = '0'

# Sanity check the group model and write out the current state so that
# you can do a local test cook.
group._copyVersions()
group._sanityCheck()
group._setGroupFlags()
group._mgr._persistGroup(group)

# You probably want to do a test cook if your groups here. It would be
# nice if mirrorball could just do this for you, but it can't right now.
# To run a test cook take a look at group._mgr._helper._checkoutCache to
# find the directory where the checkout is and then run cvc cook from
# that directory.
import epdb; epdb.st()

# Commit and build the group.
group = group.commit()
built = group.build()

import epdb; epdb.st()
