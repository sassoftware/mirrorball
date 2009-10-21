#!/usr/bin/python

import os
import sys

sys.path.insert(0, os.environ['HOME'] + '/hg/conary')
sys.path.insert(0, os.environ['HOME'] + '/hg/rhnmirror')
sys.path.insert(0, os.environ['HOME'] + '/hg/rbuilder-trunk/rpath-xmllib')
sys.path.insert(0, os.environ['HOME'] + '/hg/rbuilder-trunk/rpath-capsule-indexer')

from conary.lib import util
sys.excepthook = util.genExcepthook()

mbdir = os.path.abspath('../')
sys.path.insert(0, mbdir)

confDir = os.path.join(mbdir, 'config', 'rhel4')

from updatebot import log
from updatebot import bot
from updatebot import config

import time
import logging

slog = logging.getLogger('script')

import rhnmirror

log.addRootLogger()
cfg = config.UpdateBotConfig()
cfg.read(os.path.join(confDir, 'updatebotrc'))

obj = bot.Bot(cfg)

mcfg = rhnmirror.MirrorConfig()
mcfg.read(os.path.join(confDir, 'erratarc'))

errata = rhnmirror.Errata(mcfg)
errata.fetch()

pkgSource = obj._pkgSource
pkgSource.load()

# get mapping of advisory to errata obj
advisories = dict((x.advisory, x)
                  for x in errata.iterByIssueDate(mcfg.channels))

# get mapping of nevra to pkg obj
nevras = dict(((x.name, x.epoch, x.version, x.release, x.arch), x)
              for x in pkgSource.binPkgMap.keys() if x.arch != 'src')

# pull nevras into errata sized buckets
buckets = {}
advMap = {}
nevraMap = {}

arches = ('i386', 'i486', 'i586', 'i686', 'x86_64', 'noarch')
for e in errata.iterByIssueDate(mcfg.channels):
    bnevras = []
    bucket = []
    bucketId = None
    slog.info('processing %s' % e.advisory)
    for pkg in e.packages:
        nevra = pkg.getNevra()

        # filter out channels we don't have indexed
        channels = set([ x.label for x in pkg.channels ])
        if not set(mcfg.channels) & channels:
            continue

        # ignore arches we don't know about.
        if nevra[4] not in arches:
            continue

        # convert rhn nevra to yum nevra
        nevra = list(nevra)
        if nevra[1] is None:
            nevra[1] = '0'
        if type(nevra[1]) == int:
            nevra[1] = str(nevra[1])
        nevra = tuple(nevra)

        # move nevra to errata buckets
        if nevra in nevras:
            binPkg = nevras.pop(nevra)
            bucket.append(binPkg)
            bnevras.append(nevra)

        # nevra is already part of another bucket
        elif nevra in nevraMap:
            bucketId = nevraMap[nevra]

        # raise error if we can't find the required package
        else:
            raise KeyError

    if bucketId is None:
        bucketId = int(time.mktime(time.strptime(e.issue_date,
                                                 '%Y-%m-%d %H:%M:%S')))
        buckets[bucketId] = bucket
    else:
        buckets[bucketId].extend(bucket)

    for nevra in bnevras:
        nevraMap[nevra] = bucketId

    advMap[e.advisory] = bucketId

# separate out golden bits
other = []
golden = []
firstErrata = sorted(buckets.keys())[0]
for nevra, pkg in nevras.iteritems():
    buildtime = int(pkg.buildTimestamp)
    if buildtime < firstErrata:
        golden.append(pkg)
    else:
        other.append(pkg)

# sort by source package
srcMap = {}
for pkg in other:
    src = pkgSource.binPkgMap[pkg]
    if src not in srcMap:
        srcMap[src] = []
    srcMap[src].append(pkg)

# insert bins by buildstamp
for src, bins in srcMap.iteritems():
    buildstamp = int(sorted(bins)[0].buildTimestamp)
    if buildstamp in buckets:
        buckets[buildstamp].extend(bins)
    else:
        buckets[buildstamp] = bins

# get sources to build
buildOrder = {0: set()}
for pkg in golden:
    # lookup source package
    src = pkgSource.binPkgMap[pkg]
    buildOrder[0].add(src)

for bucketId in sorted(buckets.keys()):
    bucket = buckets[bucketId]
    buildOrder[bucketId] = set()
    for pkg in bucket:
        src = pkgSource.binPkgMap[pkg]
        buildOrder[bucketId].add(src)

import epdb; epdb.st()
