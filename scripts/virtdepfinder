#!/usr/bin/python
#
# Copyright (c) 2009 rPath, Inc.
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
sys.path.insert(0, os.environ['HOME'] + '/hg/rmake')
sys.path.insert(0, os.environ['HOME'] + '/hg/xobj/py')

from conary.lib import util
sys.excepthook = util.genExcepthook()

import logging
import updatebot.log

updatebot.log.addRootLogger()
log = logging.getLogger('test')

from updatebot import config
from updatebot.update import Updater
from updatebot import pkgsource

cfg = config.UpdateBotConfig()
cfg.read(os.environ['HOME'] + '/hg/mirrorball/config/%s/updatebotrc' % sys.argv[1] )

pkgSource = pkgsource.PackageSource(cfg)
pkgSource.load()

updater = Updater(cfg, pkgSource)

virtreqs = {}
for srcName in pkgSource.srcNameMap.iterkeys():
    if not pkgSource.srcNameMap[srcName]:
        continue
    srcPkg = updater._getLatestSource(srcName)
    for req in updater._getBuildRequiresFromPkgSource(srcPkg):
        if req[1] == 'virtual':
            if req[0] not in virtreqs:
                virtreqs[req[0]] = set()
            virtreqs[req[0]].add(srcName)

provides = {}
for binName in pkgSource.binNameMap.iterkeys():
    binPkg = updater._getLatestBinary(binName)
    for reqType in binPkg.format:
        if reqType.getName() == 'rpm:provides':
            for req in reqType.iterChildren():
                if hasattr(req, 'isspace') and req.isspace():
                    continue
                if '/' in req.name:
                    continue
                if req.name not in provides:
                    provides[req.name] = set()
                provides[req.name].add(binName)

virtreqMap = {}
for req in virtreqs.iterkeys():
    if req not in provides:
        log.warn('could not find provide %s for %s' % (req, virtreqs[req]))
        continue
    virtreqMap[req] = provides[req]

import epdb; epdb.st()
