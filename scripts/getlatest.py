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
