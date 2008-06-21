#!/usr/bin/python
#
# Copyright (c) 2008 rPath, Inc.
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
import operator

sys.path.insert(0, os.environ['HOME'] + '/hg/rpath-xmllib')
sys.path.insert(0, os.environ['HOME'] + '/hg/conary')
sys.path.insert(0, os.environ['HOME'] + '/hg/mirrorball')

from conary.lib import util
from conary.lib.sha1helper import md5String, md5ToString
from conary import rpmhelper, files, updatecmd
sys.excepthook = util.genExcepthook()

from updatebot import bot, conaryhelper, config, log
from rpmutils import readHeader

outfile = open(sys.argv[1], 'w')
cb = updatecmd.UpdateCallback()

#import cProfile
#prof = cProfile.Profile()
#prof.enable()

log.addRootLogger()
cfg = config.UpdateBotConfig()
cfg.read(os.environ['HOME'] + '/hg/mirrorball/config/sles/updatebotrc')
obj = bot.Bot(cfg)

#prof.disable()
#prof.dump_stats('report.lsprof')

conaryhelper = obj._updater._conaryhelper
conaryclient = conaryhelper._client 

pkgMap = conaryhelper.getSourceTroves(cfg.topGroup)
sources = sorted(pkgMap.keys())

for src in sources:
    srcName = src[0].split(':')[0]
    if srcName in cfg.excludePackages:
        continue
    if srcName.startswith('group-') or srcName.startswith('info-'):
        continue
    manifest = conaryhelper.getManifest(srcName)

    pathMap = {}
    # collect up a path -> rpm package map
    for rpm in manifest:
        if 'src.rpm' in rpm:
            continue
        rpmloc = '%s/%s' %(cfg.repositoryUrl, rpm)
        h = readHeader(rpmloc)
        arch = h[rpmhelper.ARCH]
        rpmname = os.path.basename(rpm)
        d = dict.fromkeys(((util.normpath(x), arch) for x in h.paths()), rpmname)
        pathMap.update(d)
    binaries = sorted(pkgMap[src])
    flist = []
    for binary in binaries:
        name, version, flavor = binary
        flavorStr = str(flavor)
        if ':' not in name:
            continue
        if 'debuginfo' in name:
            continue
        if 'is: x86_64' in str(flavorStr):
            arch = 'x86_64'
        elif 'is: x86(' in str(flavorStr):
            arch = 'i586'
        else:
            arch = 'noarch'
        print name, version, flavor
        cs = conaryclient.createChangeSet([(name,
                                            (None, None),
                                            (version, flavor), True)],
                                          withFiles=True,
                                          withFileContents=True,
                                          callback=cb)
        tcs = [x for x in cs.iterNewTroveList()][0]
        for (pathId, path, fileId, version) in sorted(tcs.newFiles):
            f = files.ThawFile(cs.getFileChange(None, fileId), pathId)
            if hasattr(f, 'contents') and f.contents:
                cont = cs.getFileContents(pathId, fileId)[1]
                md5 = md5ToString(md5String(cont.get().read()))
                try:
                    rpm = pathMap[(path, arch)]
                except KeyError:
                    # some file we added, like a tag handler
                    continue
                flist.append((binary[0], rpm, path, md5))
    # sort based on path
    flist.sort(key=operator.itemgetter(2))
    for info in flist:
        outfile.write('\t'.join(info))
        outfile.write('\n')
    outfile.flush()
