#!/usr/bin/python
#
# Copyright (c) SAS Institute, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
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
