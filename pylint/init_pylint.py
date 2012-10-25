#
# Copyright (c) rPath, Inc.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#


import os
import sys

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

# set default XMLLIB_PATH, if it was not set.
xmllibPath = setPathFromEnv('XMLLIB_PATH', 'rpath-xmllib')

# paths end up in the opposite order than they are listed.
for path in xmllibPath, rmakePath, conaryPath, mirrorballPath:
    if path in sys.path:
        sys.path.remove(path)
    sys.path.insert(0, path)
