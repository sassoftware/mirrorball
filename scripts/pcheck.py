#!/usr/bin/python

import sys
from conary.lib import util
sys.excepthook = util.genExcepthook()

from conary import versions
from conary import callbacks
from conary import conarycfg
from conary import conaryclient

cfg = conarycfg.ConaryConfiguration()
cfg.setContext('1-binary')

client = conaryclient.ConaryClient(cfg)

frmlabel = versions.VersionFromString('/conary.rpath.com@rpl:devel//1')
groupTrvs = client.repos.findTrove(['conary.rpath.com@rpl:1', ], ('group-os', frmlabel, None))

groupTrvs.sort()
groupTrvs.reverse()

trvs = [ x for x in groupTrvs if x[1] == groupTrvs[0][1] ]

labelMap = {
    versions.VersionFromString('/conary.rpath.com@rpl:devel//1'):
    versions.VersionFromString('/conary.rpath.com@rpl:devel//1-qa'),
    versions.VersionFromString('/conary.rpath.com@rpl:devel//1-xen'):
    versions.VersionFromString('/conary.rpath.com@rpl:devel//1-xen-qa'),
}

cb = conaryclient.callbacks.CloneCallback(cfg)
success, cs = client.createSiblingCloneChangeSet(
        labelMap,
        trvs,
        cloneSources=True,
        callback=cb,
        updateBuildInfo=False)

import epdb
epdb.st()



