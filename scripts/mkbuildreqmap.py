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
Generate buildRequiresMap for factory-capsule-rpm.

This script looks at all the binaries on the target label, and groups the
troves required to satisfy python and perl dependencies by the source that
requires them.
"""


import pprint
import sys
import os
import time

mirrorballDir = os.path.abspath('../')
sys.path.insert(0, mirrorballDir)

from conary.deps import deps
from updatebot import config
from updatebot import bot
from updatebot import current
from updatebot import log


# These dep classes will be inspected, all others will be ignored for buildreq
# generation purposes.
#DEP_CLASSES = (deps.PythonDependencies, deps.PerlDependencies)
DEP_CLASSES = (deps.PythonDependencies, deps.PerlDependencies, deps.RpmDependencies, deps.RpmLibDependencies)

#import epdb;epdb.st()

logfile = '%s_%s.log' % (sys.argv[0], time.strftime('%Y-%m-%d_%H%M%S'))

log.addRootLogger(logfile)


def main(obj):
    helper = obj._updater._conaryhelper

    print "Collecting RPM list"
    rpmBins = set()
    for name, verDict in helper._getLatestTroves().iteritems():
        if not name.endswith(':rpm'):
            continue
        for version, flavors in verDict.iteritems():
            for flavor in flavors:
                rpmBins.add((name, version, flavor))
    rpmBins = sorted(rpmBins)

    total = len(rpmBins)
    n = 0
    numBins = 100
    # Map dep to the troves that provide it
    provMap = {}
    # Map trove to the deps it requires
    reqMap = {}
    while rpmBins:
        print "Analyzing requirements (%d/%d)" % (n, total)
        toFetch, rpmBins = rpmBins[:numBins], rpmBins[numBins:]
        n += len(toFetch)

        fetchReqs = helper._repos.getDepsForTroveList(toFetch)
        for binTup, (provs, reqs) in zip(toFetch, fetchReqs):
            for depClass in DEP_CLASSES:
                for dep in provs.iterDepsByClass(depClass):
                    provMap.setdefault(dep, set()).add(binTup)
                for dep in reqs.iterDepsByClass(depClass):
                    reqMap.setdefault(binTup, set()).add(dep)

    # For each source, collect all the troves that provide a dep that its built
    # binaries require.
    allRequiringBins = set(reqMap)
    print "Collecting source list for %d troves" % len(allRequiringBins)
    srcNameMap = helper.getSourceVersions(allRequiringBins)
    buildRequiresMap = {}
    for srcTup, binTups in srcNameMap.iteritems():
        name = srcTup[0]
        assert name.endswith(':source')
        name = name.split(':')[0]

        reqTroves = set()
        for binTup in binTups:
            for dep in reqMap[binTup]:
                for provTup in provMap.get(dep, set()):
                    if provTup[0].split(':')[0] == name:
                        # Reqs between subpackages of the same source aren't
                        # interesting for build requirements, because neither has been
                        # built yet.
                        continue
                    reqTroves.add(provTup[0])

        reqTroves.discard('perl:rpm')
        reqTroves.discard('python:rpm')
        reqTroves.discard('python-test:rpm')
        if reqTroves:
            buildRequiresMap[name] = reqTroves

    print 'buildRequiresMap = ',
    pprint.PrettyPrinter().pprint(buildRequiresMap)

    #import epdb;epdb.st()

if __name__ == '__main__':
    from conary.lib import util
    sys.excepthook = util.genExcepthook()

    cfg = config.UpdateBotConfig()
    cfg.read(os.path.abspath('../') + '/config/%s/updatebotrc' % sys.argv[1])
    if cfg.updateMode == 'current':
        obj = current.Bot(cfg)
    if cfg.updateMode == 'latest':
        obj = bot.Bot(cfg)

    main(obj)
