#!/usr/bin/python
#
# Copryright (c) 2008 rPath, Inc.
#

"""
Script for cooking groups defined in the updatebot config.
"""

import os
import sys

sys.path.insert(0, os.environ['HOME'] + '/hg/rpath-xmllib')
sys.path.insert(0, os.environ['HOME'] + '/hg/conary')
sys.path.insert(0, os.environ['HOME'] + '/hg/mirrorball')

from updatebot import log
from updatebot import build
from updatebot import config

log.addRootLogger()
cfg = config.UpdateBotConfig()
cfg.read(os.environ['HOME'] + '/hg/mirrorball/config/updatebotrc')

builder = build.Builder(cfg)

grpTrvs = set()
for flavor in cfg.groupFlavors:
    grpTrvs.add((cfg.topSourceGroup[0], cfg.topSourceGroup[1], flavor))
grpTrvMap = builder.build(grpTrvs)

print "built:\n"

def displayTrove(nvf):
    flavor = ''
    if nvf[2] is not None:
        flavor = '[%s]' % nvf[2]

    return '%s=%s%s' % (nvf[0], nvf[1], flavor)

for srcTrv in grpTrvMap.iterkeys():
    print displayTrove(srcTrv)
    for binTrv in grpTrvMap[srcTrv]:
        print "\t", displayTrove(binTrv)
