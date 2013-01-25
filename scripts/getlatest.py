#!/usr/bin/python
#
# Copyright (c) SAS Institute, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
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
