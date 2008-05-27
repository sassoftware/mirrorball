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

import epdb
epdb.st()

# set default SLEESTACK_PATH, if it was not set.
parDir = '/'.join(os.path.realpath(__file__).split('/')[:-2])
parDir = os.path.dirname(parDir)
mirrorballPath = os.getenv('SLEESTACK_PATH', parDir)
os.environ['SLEESTACK_PATH'] = mirrorballPath

def setPathFromEnv(variable, directory):
    parDir = '/'.join(os.path.realpath(__file__).split('/')[:-3])
    parDir = os.path.dirname(parDir) + '/' + directory
    thisPath = os.getenv(variable, parDir)
    os.environ[variable] = thisPath
    if thisPath not in sys.path:
        sys.path.insert(0, thisPath)
    return thisPath

# set default CONARY_PATH, if it was not set.
conaryPath = setPathFromEnv('CONARY_PATH', 'conary')

# set default RMAKE_PATH, if it was not set.
rmakePath = setPathFromEnv('RMAKE_PATH', 'rmake')

for path in rmakePath, conaryPath, mirrorballPath:
    if path in sys.path:
        sys.path.remove(path)
    sys.path.insert(0, path)
