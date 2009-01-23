#!/usr/bin/python

import sys
from conary.lib import util
sys.excepthook = util.genExcepthook()

from conary.lib import log
from conary import trove
from conary import versions
from conary import callbacks
from conary import conarycfg
from conary import conaryclient

cfg = conarycfg.ConaryConfiguration(True)
cfg.setContext('1-binary')

client = conaryclient.ConaryClient(cfg)

frmlabel = versions.VersionFromString('/conary.rpath.com@rpl:devel//1')
groupTrvs = client.repos.findTrove(['conary.rpath.com@rpl:1', ], ('group-os', frmlabel, None))

groupTrvs.sort()
groupTrvs.reverse()

grpTrvs = [ x for x in groupTrvs if x[1] == groupTrvs[0][1] ]


# Find all of the troves in the groups that are to be promoted.
log.info('Create group changesets')
grpCsReq = [(x, (None, None), (y, z), True) for x, y, z in grpTrvs ]
grpCs = client.createChangeSet(grpCsReq, withFiles=False, withFileContents=False, recurse=False)

oldTrvSpecs = set()
for topLevelCs in grpCs.iterNewTroveList():
    trv = trove.Trove(topLevelCs, skipIntegrityChecks=True)
    oldTrvSpecs.update(set([ x for x in trv.iterTroveList(weakRefs=True, strongRefs=True) ]))


# Build mapping of frumptuus.
labelMap = {
    versions.VersionFromString('/conary.rpath.com@rpl:devel//1'):
    versions.VersionFromString('/conary.rpath.com@rpl:devel//1-qa'),
    versions.VersionFromString('/conary.rpath.com@rpl:1'):
    versions.VersionFromString('/conary.rpath.com@rpl:1-qa'),
    versions.VersionFromString('/conary.rpath.com@rpl:devel//1-xen'):
    versions.VersionFromString('/conary.rpath.com@rpl:devel//1-xen-qa'),
    versions.VersionFromString('/conary.rpath.com@rpl:devel//1-vmware'):
    versions.VersionFromString('/conary.rpath.com@rpl:devel//1-vmware-qa'),
}

# List of labels that should not be promoted.
hiddenLabels = [
    versions.Label('conary.rpath.com@rpl:1-compat'),
]


# Find troves that have labels that are not in the label map.
log.info('Searching for troves that will not be promoted')
branches = labelMap.keys()
for name, version, flavor in sorted(oldTrvSpecs):
    if version.branch() not in branches:
        match = False
        for label in hiddenLabels:
             if label in version.versions:
                match = True
        if not match:
            log.warning('not promoting %s=%s[%s]' % (name, version, flavor)) 


# Ask before moving on.
okay = conaryclient.cmdline.askYn('continue with clone? [y/N]', default=False)
if not okay:
    sys.exit(0)

# Make the promote changeset.
log.info('Creating promote changeset')
cb = conaryclient.callbacks.CloneCallback(cfg, 'automated commit')
success, cs = client.createSiblingCloneChangeSet(
        labelMap,
        grpTrvs,
        cloneSources=True,
        callback=cb,
        updateBuildInfo=False)

# Check status
if not success:
    log.critical('Failed to create promote changeset')
    sys.exit(1)

# Ask before committing.
okay = conaryclient.cmdline.askYn('commit changset? [y/N]', default=False)

# Commit changeset.
if okay:
    client.repos.commitChangeSet(cs, callback=callback)
