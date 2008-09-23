#!/usr/bin/python
# -*- mode: python -*-
#
# Copyright (c) 2006-2007 rPath, Inc.  All Rights Reserved.
#
# W0603: using the global statement
#pylint: disable-msg=W0603
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
import bootstrap

archivePath = None
testPath = None
pluginPath = None

conaryDir = None
_setupPath = None
_individual = False

def isIndividual():
    return _individual

def setup():
    global _setupPath
    if _setupPath:
        return _setupPath
    global testPath
    global archivePath
    global conaryDir
    global pluginPath

    def setPathFromEnv(variable, directory):
        parDir = os.path.dirname(os.path.realpath(__file__))
        if not directory.startswith('/'):
            parDir = os.path.dirname(parDir) + '/' + directory
        else:
            parDir = directory
        thisPath = os.getenv(variable, parDir)
        os.environ[variable] = thisPath
        if thisPath in sys.path:
            sys.path.remove(thisPath)
        sys.path.insert(0, thisPath)
        return thisPath

    testutilsPath = setPathFromEnv('TESTUTILS_PATH', '../testutils')
    conaryDir = setPathFromEnv('CONARY_PATH', '../conary')
    conaryTestPath = setPathFromEnv('CONARY_TEST_PATH', '../conary-test')
    setPathFromEnv('CONARY_POLICY_PATH', '/usr/lib/conary/policy')
    mirrorballPath = setPathFromEnv('SLEESTACK_PATH', '')

    rmakePath = setPathFromEnv('RMAKE_PATH', '../rmake')
    rmakeTestPath = setPathFromEnv('RMAKE_TEST_PATH', '../rmake-private')
    xmllibPath = setPathFromEnv('XMLLIB_PATH', '../rpath-xmllib')
    pluginPath = os.path.realpath(rmakeTestPath + '/rmake_plugins')

    # Insert the following paths into the python path and sys path in
    # listed order.
    paths = (mirrorballPath, rmakePath, conaryDir, conaryTestPath,
             rmakeTestPath, xmllibPath, testutilsPath)
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
        #pylint: disable-msg=E1103
        if os.path.exists(serverDir) and not os.path.access(serverDir, os.W_OK):
            serverDir = serverDir + '-' + pwd.getpwuid(os.getuid())[0]
        os.environ['SERVER_FILE_PATH'] = serverDir

    from testrunner import resources, testhelp
    testPath = testhelp.getTestPath()
    archivePath = testPath + '/archive'
    resources.archivePath = archivePath

    resources.pluginPath = pluginPath
    resources.rmakePath = rmakePath

    # W0621 - redefining name util, W0404 - reimporting util
    #pylint: disable-msg=W0621,W0404
    from conary.lib import util
    sys.excepthook = util.genExcepthook(True)

    # import tools normally expected in testsuite.
    sys.modules[__name__].context = testhelp.context
    sys.modules[__name__].TestCase = testhelp.TestCase
    sys.modules[__name__].findPorts = testhelp.findPorts
    sys.modules[__name__].SkipTestException = testhelp.SkipTestException

    _setupPath = testPath
    return testPath


_individual = False


def getCoverageDirs(*_):
    codePath = os.environ['SLEESTACK_PATH'].rstrip('/')
    coverageDirs = [ 'aptmd', 'repomd', 'rpmutils', 'updatebot' ]
    return [ os.path.join(codePath, x) for x in coverageDirs ]

def getCoverageExclusions(*_):
    return ['test/.*']

def sortTests(tests):
    order = {'rbuild_test.smoketest': 0, 
             'rbuild_test.unit_test': 1,
             'rbuild_test.functionaltest': 2}
    maxNum = len(order)
    tests = [ (test, test.index('test')) for test in tests]
    tests = sorted((order.get(test[:index+4], maxNum), test)
                   for (test, index) in tests)
    tests = [ x[1] for x in tests ]
    return tests

def main(argv=None, individual=True):
    from testrunner import testhelp
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
    # unused import coveragehook
    # redefining util from outer scope
    #pylint: disable-msg=W0611,W0621
    from conary.lib import util
    from conary.lib import coveragehook
    sys.excepthook = util.genExcepthook(True)
    main(sys.argv, individual=False)
