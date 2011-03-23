#!/usr/bin/python
#
# Copyright (c) 2011 rPath, Inc.
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
Script for querying latest version of a package from each platform.
"""

import os
import sys

mirrorballDir = os.path.abspath('../')
sys.path.insert(0, mirrorballDir)

if 'CONARY_PATH' in os.environ:
    sys.path.insert(0, os.environ['CONARY_PATH'])

import conary
import updatebot

print >>sys.stderr, 'using conary from', os.path.dirname(conary.__file__)
print >>sys.stderr, 'using updatebot from', os.path.dirname(updatebot.__file__)

from conary.lib import util
sys.excepthook = util.genExcepthook()

from updatebot import log
from updatebot import config
from updatebot import conaryhelper

def usage():
    print 'usage: %s <pkgname>' % sys.argv[0]
    sys.exit(1)

def getPlatformConfigs(cfgDir):
    platformConfigs = []
    for dname in os.listdir(cfgDir):
        conf = os.path.join(cfgDir, dname, 'updatebotrc')
        if os.path.exists(conf):
            cfg = config.UpdateBotConfig()
            cfg.read(conf)
            platformConfigs.append(cfg)
    return platformConfigs

def display(cfg, pkg, nvfs):
    print cfg.platformName, cfg.upstreamProductVersion
    for nvf in nvfs:
        print '  %s=%s[%s]' % nvf

if len(sys.argv) != 2:
    usage()

log.addRootLogger()

pkgName = sys.argv[1]
platforms = getPlatformConfigs(os.path.join(mirrorballDir, 'config'))

results = []
for cfg in platforms:
    helper = conaryhelper.ConaryHelper(cfg)
    spec = (pkgName, cfg.targetLabel, None)

    try:
        nvf = helper.findTrove(spec)
    except:
        nvf = []

    if nvf:
        results.append((cfg, pkgName, nvf))

for res in results:
    display(*res)
