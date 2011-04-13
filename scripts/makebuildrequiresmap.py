#!/usr/bin/python
"""
Generate buildRequiresMap for factory-capsule-rpm.

This script looks at all the binaries on the target label, and groups the
troves required to satisfy python and perl dependencies by the source that
requires them.
"""

from _scriptsetup import getBot

import logging
import pprint
import sys
from conary.deps import deps

from updatebot import config
from updatebot import OrderedBot

log = logging.getLogger('mkbuildreqsmap')

# These dep classes will be inspected, all others will be ignored for buildreq
# generation purposes.
DEP_CLASSES = (deps.PythonDependencies, deps.PerlDependencies)

def main():
    bot = getBot(OrderedBot, None)
    helper = bot._updater._conaryhelper

    log.info("Collecting RPM list")
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
        log.info("Analyzing requirements (%d/%d)", n, total)
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
    log.info("Collecting source list for %d troves", len(allRequiringBins))
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

if __name__ == '__main__':
    main()
