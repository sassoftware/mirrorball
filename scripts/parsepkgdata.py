#!/usr/bin/python
#
# Copyright (c) 2009 rPath, Inc.
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

"""
Script for walking a tree of rpms and building the metadata needed to detect
repository state based on the contents of such a directory.
"""

from header import *

from updatebot import log as logger
from updatebot.pkgsource import rpmSource

log = logger.addRootLogger()

path = sys.argv[2]

obj = RpmDirectoryIndexer(cfg, path)
obj.loadFromUrl(sys.argv[2], basePath=sys.argv[3])

nv = [ x for x in obj.iterPackageSet() ]

import epdb; epdb.st()
