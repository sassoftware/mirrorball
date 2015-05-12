#!/usr/bin/python

import sys
import os

from conary.lib import util
sys.excepthook = util.genExcepthook()

sys.path.insert(0, os.path.abspath('../'))

from updatebot import bot, config, log

log.addRootLogger()
cfg = config.UpdateBotConfig()
cfg.read(os.path.abspath('../') + '/config/%s/updatebotrc' % sys.argv[1])
obj = bot.Bot(cfg)

obj._pkgSource.load()

pkgNames = sys.argv[2:]

if not pkgNames:
    pkgNames = cfg.package

# Have to look up the src to get the src package name right
# So we look all the bins and create a srcMap this way if we ask 
# for python-slip-dbus we create a src for python-slip which in 
# turn produces python-slip and python-slip-dbus binaries.

srcMap = {}
for pkgName in pkgNames:
    srcPkg = obj._updater._getPackagesToImport(pkgName)
    srcMap.setdefault(srcPkg, set()).add(pkgName)


for src in sorted(srcMap):
    print src.name

