#!/usr/bin/python
#
# Copryright (c) 2008 rPath, Inc.
#

import os
import sys

sys.path.insert(0, os.environ['HOME'] + '/hg/rpath-xmllib')
sys.path.insert(0, os.environ['HOME'] + '/hg/conary')
sys.path.insert(0, os.environ['HOME'] + '/hg/mirrorball')

from conary.lib import util
sys.excepthook = util.genExcepthook()

from conary.build import use
from updatebot import conaryhelper, config, log

log.addRootLogger()
cfg = config.UpdateBotConfig()
cfg.read(os.environ['HOME'] + '/hg/mirrorball/config/sles/updatebotrc')
helper = conaryhelper.ConaryHelper(cfg)

license = """\
#
# Copyright (c) 2008 rPath, Inc.
# This file is distributed under the terms of the MIT License.
# A copy is available at http://www.rpath.com/permanent/mit-license.html
#

"""

for name, version, flavor in helper.getSourceTroves(cfg.topGroup):
    if version.trailingLabel().asString() != cfg.topGroup[1]:
        continue

    if name.startswith('group-') or \
       name.startswith('info-') or \
       name.startswith('factory-'):
        continue

    name = name.split(':')[0]

    pkgdir = helper._checkout(name)
    recipe = os.path.join(pkgdir, '%s.recipe' % name)
    if os.path.exists(recipe):
        contents = open(recipe).read()
        if contents.startswith('#'):
            continue

        fh = open(recipe, 'w')
        fh.write(license)
        fh.write(contents)
        fh.close()

        use.setBuildFlagsFromFlavor(name, helper._ccfg.buildFlavor,
                                    error=False)

        helper._commit(pkgdir, 'Add recipe copyright license')
