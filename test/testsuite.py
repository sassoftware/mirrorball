#!/usr/bin/python
# -*- mode: python -*-
#
# Copyright (c) 2006-2007 rPath, Inc.  All Rights Reserved.
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

import sys
import os
import pwd

archivePath = None
testPath = None
pluginPath = None
nodePath = None

conaryDir = None
_setupPath = None
_individual = False

def isIndividual():
    global _individual
    return _individual

def setup():
    global _setupPath
    if _setupPath:
        return _setupPath
    global testPath
    global archivePath
    global pluginPath
    global nodePath
    global rmakePath

    # set default SLEESTACK_PATH, if it was not set.
    parDir = '/'.join(os.path.realpath(__file__).split('/')[:-1])
    parDir = os.path.dirname(parDir)
    mirrorballPath = os.getenv('SLEESTACK_PATH', parDir)
    os.environ['SLEESTACK_PATH'] = mirrorballPath

    def setPathFromEnv(variable, directory):
        parDir = '/'.join(os.path.realpath(__file__).split('/')[:-2])
        parDir = os.path.dirname(parDir) + '/' + directory
        thisPath = os.getenv(variable, parDir)
        os.environ[variable] = thisPath
        if thisPath not in sys.path:
            sys.path.insert(0, thisPath)
        return thisPath

    # set default CONARY_PATH, if it was not set.
    conaryPath = setPathFromEnv('CONARY_PATH', 'conary')

    # set default CONARY_TEST_PATH, if it was not set.
    conaryTestPath = setPathFromEnv('CONARY_TEST_PATH', 'conary-test')

    # set default RMAKE_PATH, if it was not set.
    rmakePath = setPathFromEnv('RMAKE_PATH', 'rmake')

    # set default RMAKE_TEST_PATH, if it was not set.
    rmakeTestPath = setPathFromEnv('RMAKE_TEST_PATH', 'rmake-private/test')

    testDir = os.path.dirname(os.path.realpath(__file__))

    # Insert the following paths into the python path and sys path in
    # listed order.
    paths = (mirrorballPath, rmakePath, testDir, conaryPath, conaryTestPath,
             rmakeTestPath)
    pythonPath = os.environ.get('PYTHONPATH', "")
    for p in reversed(paths):
        if p in sys.path:
            sys.path.remove(p)
        sys.path.insert(0, p)
    for p in paths:
        if p not in pythonPath:
            pythonPath = os.pathsep.join((pythonPath, p))
    os.environ['PYTHONPATH'] = pythonPath

    if isIndividual():
        serverDir = '/tmp/conary-server'
        if os.path.exists(serverDir) and not os.path.access(serverDir, os.W_OK):
            serverDir = serverDir + '-' + pwd.getpwuid(os.getuid())[0]
        os.environ['SERVER_FILE_PATH'] = serverDir

    invokedAs = sys.argv[0]
    if invokedAs.find("/") != -1:
        if invokedAs[0] != "/":
            invokedAs = os.getcwd() + "/" + invokedAs
        path = os.path.dirname(invokedAs)
    else:
        path = os.getcwd()

    import testhelp
    from conary_test import resources
    testPath = testhelp.getTestPath()
    archivePath = testPath + '/' + "archive"
    resources.archivePath = archivePath

    pluginPath = os.path.realpath(testPath + '/../../rmake-private/rmake_plugins')
    nodePath = os.path.realpath(pluginPath + '/..')
    if nodePath not in sys.path:
        sys.path.insert(0, nodePath)

    global conaryDir
    conaryDir = os.environ['CONARY_PATH']

    from conary.lib import util
    sys.excepthook = util.genExcepthook(True)

    # import tools normally expected in testsuite.
    from testhelp import context, TestCase, findPorts, SkipTestException
    sys.modules[__name__].context = context
    sys.modules[__name__].TestCase = TestCase
    sys.modules[__name__].findPorts = findPorts
    sys.modules[__name__].SkipTestException = SkipTestException

    _setupPath = testPath
    return testPath

_individual = False

def isIndividual():
    global _individual
    return _individual

def getCoverageDirs(handler, environ):
    basePath = os.environ['SLEESTACK_PATH']
    coverageDirs = [ 'updateBot', 'rpmimport', 'repomd', ]

    coveragePath = []
    for path in coverageDirs:
        covaregePath.append(os.path.normpath(os.path.join(basePath, path)))

    return coveragePath

def getCoverageExclusions(self, environ):
    return ['test/.*']

def sortTests(tests):
    order = {'smoketest': 0, 
             'unit_test' :1,
             'functionaltest':2}
    maxNum = len(order)
    tests = [ (test,test.index('test')) for test in tests]
    tests = sorted((order.get(test[:index+4], maxNum), test)
                   for (test, index) in tests)
    tests = [ x[1] for x in tests ]
    return tests

def main(argv=None, individual=True):
    import testhelp
    handlerClass = testhelp.getHandlerClass(testhelp.ConaryTestSuite,
                                            getCoverageDirs,
                                            getCoverageExclusions,
                                            sortTests)
    global _individual
    _individual = individual
    if argv is None:
        argv = list(sys.argv)
    topdir = testhelp.getTestPath()
    cwd = os.getcwd()
    if cwd != topdir and cwd not in sys.path:
        sys.path.insert(0, cwd)

    handler = handlerClass(individual=individual, topdir=topdir,
                           testPath=testPath, conaryDir=conaryDir)
    results = handler.main(argv)
    if results is None:
        sys.exit(0)
    sys.exit(not results.wasSuccessful())

if __name__ == '__main__':
    setup()
    from conary.lib import util
    from conary.lib import coveragehook
    sys.excepthook = util.genExcepthook(True)
    main(sys.argv, individual=False)
