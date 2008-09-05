#!/usr/bin/python

import os
import sys
from conary.lib import util
sys.excepthook = util.genExcepthook()

sys.path.insert(0, os.environ['HOME'] + '/hg/rpath-xmllib')
sys.path.insert(0, os.environ['HOME'] + '/hg/conary')
sys.path.insert(0, os.environ['HOME'] + '/hg/mirrorball')

import logging
import updatebot.log

updatebot.log.addRootLogger()
log = logging.getLogger('test')

import aptmd
import repomd
from updatebot import config
from updatebot import pkgsource

cfg = config.UpdateBotConfig()
cfg.read(os.environ['HOME'] + '/hg/mirrorball/config/sles/updatebotrc')

pkgSource = pkgsource.PackageSource(cfg)

if cfg.repositoryFormat == 'apt':
    client = aptmd.Client(cfg.repositoryUrl)
    for path in cfg.repositoryPaths:
        log.info('loading %s' % path)
        pkgSource.loadFromClient(client, path)
else:
    for path in cfg.repositoryPaths:
        client = repomd.Client(cfg.repositoryUrl + '/' + path)
        log.info('loading %s' % path)
        pkgSource.loadFromClient(client, path)
        
pkgSource.finalize()

import epdb; epdb.st()
