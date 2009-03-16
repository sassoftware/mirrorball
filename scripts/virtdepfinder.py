#!/usr/bin/python2.6

import os
import sys

sys.path.insert(0, os.environ['HOME'] + '/hg/26/rpath-xmllib')
sys.path.insert(0, os.environ['HOME'] + '/hg/26/conary')
sys.path.insert(0, os.environ['HOME'] + '/hg/26/mirrorball')
sys.path.insert(0, os.environ['HOME'] + '/hg/26/rmake')
sys.path.insert(0, os.environ['HOME'] + '/hg/26/epdb')
sys.path.insert(0, os.environ['HOME'] + '/hg/26/xobj/py')

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
cfg.read(os.environ['HOME'] + '/hg/26/mirrorball/config/%s/updatebotrc' % sys.argv[1] )

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
