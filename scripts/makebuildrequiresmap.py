#!/usr/bin/python
"""
Generate buildRequiresMap for factory-capsule-rpm.

This script looks at all the binaries on the target label, and groups the
troves required to satisfy python and perl dependencies by the source that
requires them.
"""

from _scriptsetup import getBot

import bz2
import logging
import pprint
import sys
from conary.deps import deps
from xml.dom import minidom

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
    buildRequiresMap = {}
    allRequiringBins = set(reqMap)
    log.info("Collecting source list for %d troves", len(allRequiringBins))
    srcNameMap = helper.getSourceVersions(allRequiringBins)
    toCheckLogs = set()
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

        if reqTroves:
            version = list(binTups)[0][1]
            flavors = set(x[2] for x in binTups)
            debugTups = set((name + ':debuginfo', version, x) for x in flavors)
            toCheckLogs.update(debugTups)

        reqTroves.discard('perl:rpm')
        reqTroves.discard('python:rpm')
        reqTroves.discard('python-test:rpm')
        if reqTroves:
            buildRequiresMap[name] = reqTroves

    toCheckLogs = sorted(toCheckLogs)
    n = 0
    total = len(toCheckLogs)
    while toCheckLogs:
        log.info("Analyzing build logs (%d/%d)", n, total)
        toFetch, toCheckLogs = toCheckLogs[:numBins], toCheckLogs[numBins:]
        n += len(toFetch)
        addExtraRequires(buildRequiresMap, toFetch, helper._client)

    print 'buildRequiresMap = ',
    pprint.PrettyPrinter().pprint(buildRequiresMap)


def addExtraRequires(buildRequiresMap, binTups, client):
    jobs = [(x[0], (None, None), (x[1], x[2]), True) for x in binTups]
    cs = client.createChangeSet(jobs, withFiles=True, withFileContents=True,
            recurse=False)
    logMap = {}
    for trvCs in cs.iterNewTroveList():
        pkgName = trvCs.getName().split(':')[0]
        for pathId, path, fileId, fileVer in trvCs.getNewFileList():
            if path.endswith('-xml.bz2'):
                cs.reset()
                _, cont = cs.getFileContents(pathId, fileId)
                logContents = cont.get().read()
                logMap[pkgName] = logContents
                break

    for pkgName, logContents in logMap.items():
        dom = minidom.parseString(bz2.decompress(logContents))
        for node in dom.childNodes[0].childNodes:
            if getattr(node, 'tagName', '') != 'record':
                continue
            desc = message = None
            for subnode in node.childNodes:
                if getattr(subnode, 'tagName', '') == 'descriptor':
                    desc = subnode.childNodes[0].nodeValue
                elif getattr(subnode, 'tagName', '') == 'message':
                    message = subnode.childNodes[0].nodeValue
            if desc == 'cook.build.policy.ERROR_REPORTING.reportExcessBuildRequires.excessBuildRequires':
                excessReqs = message.split()
                if 'python-setuptools:rpm' not in excessReqs:
                    buildRequiresMap.setdefault(pkgName, set()).add(
                            'python-setuptools:rpm')

if __name__ == '__main__':
    main()
