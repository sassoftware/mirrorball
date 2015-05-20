#!/usr/bin/python
#
# Copyright (c) SAS Institute, Inc.
#

"""
Script to set product info on a group.
"""

import sys
import epdb
sys.excepthook = epdb.excepthook()

import json

from conary import trove
from conary import conarycfg
from conary import conaryclient
from conary.conaryclient import cmdline

def setProductInfo(trvSpec, info):
    trvSpec = cmdline.parseTroveSpec(trvSpec)

    cfg = conarycfg.ConaryConfiguration(True)
    client = conaryclient.ConaryClient(cfg)
    repos = client.getRepos()

    nvfs = repos.findTrove(None, trvSpec)
    if not len(nvfs):
        print >>sys.stderr, 'did not find any troves matching %s' % trvSpec
        return 1

    nvf = nvfs[0]

    trv = repos.getTrove(*nvf)
    md = trv.troveInfo.metadata

    keyValue = md.get(1).get('keyValue')
    if not keyValue:
        mi = trove.MetadataItem()
        md.addItem(mi)
        keyValue = mi.keyValue

    keyValue['product_info'] = json.dumps(info)

    repos.setTroveInfo([(nvf, trv.troveInfo), ])

def usage(args):
    print >>sys.stderr, 'usage: %s <trove spec> <display name>' % args[0]
    return 1

def main(args):
    if len(args) != 3:
        return usage(args)

    troveSpec = args[1]
    displayName = args[2]

    setProductInfo(troveSpec, {
        'displayName': displayName,
    })

    return 0

if __name__ == '__main__':
    sys.exit(main(sys.argv))
