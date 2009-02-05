#!/usr/bin/python2.6

import os
import sys

sys.path.insert(0, os.environ['HOME'] + '/hg/26/rpath-xmllib')
sys.path.insert(0, os.environ['HOME'] + '/hg/26/conary')
sys.path.insert(0, os.environ['HOME'] + '/hg/26/mirrorball')
sys.path.insert(0, os.environ['HOME'] + '/hg/26/rmake')
sys.path.insert(0, os.environ['HOME'] + '/hg/26/epdb')

from conary.lib import util
sys.excepthook = util.genExcepthook()

import logging
import updatebot.log

updatebot.log.addRootLogger()
log = logging.getLogger('test')

import aptmd
import repomd
from updatebot import config
from updatebot import pkgsource

cfg = config.UpdateBotConfig()
cfg.read(os.environ['HOME'] + '/hg/26/mirrorball/config/sles/updatebotrc')

pkgSource = pkgsource.PackageSource(cfg)
pkgSource.load()

import epdb; epdb.st()
