#!/usr/bin/python
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

import testsetup

import mock
import slehelp

from conary import trove
from conary import versions
from conary.deps import deps

from updatebot import errors
from updatebot import conaryhelper

class ConaryHelperTest(slehelp.Helper):
    label = 'foo.rpath.com@rpath:foo-devel'
    findTroveReturn = (
        ('group-foo',
         versions.VersionFromString('/' + label + '/1.0-1-1'),
         deps.parseFlavor('is:x86'),
        ),
        ('group-foo',
         versions.VersionFromString('/' + label + '/1.0-1-1'),
         deps.parseFlavor('is:x86 x86_64'),
        ),
        ('group-foo',
         versions.VersionFromString('/' + label + '/1.0-2-1'),
         deps.parseFlavor('is:x86'),
        ),
        ('group-foo',
         versions.VersionFromString('/' + label + '/1.0-2-1'),
         deps.parseFlavor('is:x86 x86_64'),
        ),
    )

    findTroveReturn[0][1].setTimeStamps((1.0, ))
    findTroveReturn[1][1].setTimeStamps((1.0, ))
    findTroveReturn[2][1].setTimeStamps((2.0, ))
    findTroveReturn[3][1].setTimeStamps((2.0, ))

    def testGetConaryConfig(self):
        helper = conaryhelper.ConaryHelper(self.updateBotCfg)
        ccfg = helper.getConaryConfig()
        self.failUnless(ccfg is helper._ccfg)

    def testGetSourceTroves(self):
        group = ('group-foo', self.label, None)
        helper = conaryhelper.ConaryHelper(self.updateBotCfg)
        helper._ccfg.buildLabel = self.label

        mockRepos = mock.MockObject(stableReturnValues=True)
        mockRepos.findTrove._mock.setReturn(self.findTroveReturn,
            helper._ccfg.buildLabel, group)
        self.mock(helper, '_repos', mockRepos)

        mockFindLatest = mock.MockObject(stableReturnValues=True)
        mockFindLatest._mock.setReturn(self.findTroveReturn[2:],
                                       self.findTroveReturn)
        self.mock(helper, '_findLatest', mockFindLatest)

        getSourceTrovesReturn1 = set([
            ('foo:source',
             versions.VersionFromString('/' + self.label + '/1.0-1'),
             None
            ),
        ])
        getSourceTrovesReturn2 = set([
            ('bar:source',
             versions.VersionFromString('/' + self.label + '/1.0-1'),
             None
            ),
        ])
        mockGetSourceTroves = mock.MockObject(stableReturnValues=True)
        mockGetSourceTroves._mock.setReturn(getSourceTrovesReturn1,
                                            self.findTroveReturn[2])
        mockGetSourceTroves._mock.setReturn(getSourceTrovesReturn2,
                                            self.findTroveReturn[3])
        self.mock(helper, '_getSourceTroves', mockGetSourceTroves)

        # normal case
        srcTrvs = helper.getSourceTroves(group)
        self.failUnlessEqual(type(set()), type(srcTrvs))
        self.failUnless(srcTrvs.issuperset(getSourceTrovesReturn1))
        self.failUnless(srcTrvs.issuperset(getSourceTrovesReturn2))
        mockRepos.findTrove._mock.assertCalled(helper._ccfg.buildLabel, group)
        mockFindLatest._mock.assertCalled(self.findTroveReturn)
        mockGetSourceTroves._mock.assertCalled(self.findTroveReturn[2])
        mockGetSourceTroves._mock.assertCalled(self.findTroveReturn[3])

        # exception case
        mockFindLatest._mock.setReturn(self.findTroveReturn[1:],
                                       self.findTroveReturn)
        self.failUnlessRaises(errors.TooManyFlavorsFoundError,
                              helper.getSourceTroves, group)
        mockRepos.findTrove._mock.assertCalled(helper._ccfg.buildLabel, group)
        mockFindLatest._mock.assertCalled(self.findTroveReturn)
        mockGetSourceTroves._mock.assertNotCalled()

    def testFindLatest(self):
        test1 = list(self.findTroveReturn)
        testret1 = self.findTroveReturn[2:]

        test2 = list(self.findTroveReturn)
        test2.reverse()
        testret2 = test2[:2]

        test3 = [self.findTroveReturn[2], self.findTroveReturn[0],
                 self.findTroveReturn[3], self.findTroveReturn[1]]
        testret3 = [test1[2], test1[3]]

        helper = conaryhelper.ConaryHelper(self.updateBotCfg)
        for test, result in ((test1, testret1),
                             (test2, testret2),
                             (test3, testret3)):
            ret = helper._findLatest(test)
            for res in result:
                self.failUnless(res in ret)

    def testInternalGetSourceTroves(self):
        trvSpec = self.findTroveReturn[3]
        cl = [ (trvSpec[0], (None, None), (trvSpec[1], trvSpec[2]), True) ]

        helper = conaryhelper.ConaryHelper(self.updateBotCfg)

        mockChangeSet = mock.MockObject()
        mockClient = mock.MockObject(stableReturnValues=True)
        mockClient.createChangeSet._mock.setReturn(mockChangeSet, cl,
            withFiles=False, withFileContents=False, recurse=False)
        self.mock(helper, '_client', mockClient)

        mockSourceVersion = mock.MockObject()
        mockVersion = mock.MockObject(stableReturnValues=True)
        mockVersion.getSourceVersion._mock.setReturn(mockSourceVersion)

        nvfs = [('foo:runtime', mockVersion, None),
                ('bar:runtime', mockVersion, None),
                ('baz:devel', mockVersion, None)]

        mockTrove = mock.MockObject(stableReturnValues=True)
        mockTrove.iterTroveList._mock.setReturn(nvfs, weakRefs=True,
                                                      strongRefs=True)

        mockGetTrove = mock.MockObject(stableReturnValues=True)
        mockGetTrove._mock.setReturn(mockTrove, mockChangeSet, *trvSpec)
        self.mock(helper, '_getTrove', mockGetTrove)

        mockSource1 = mock.MockObject(stableReturnValues=True)
        mockSource1._mock.setReturn('foo:source')
        mockSource2 = mock.MockObject(stableReturnValues=True)
        mockSource2._mock.setReturn('bar:source')
        mockSource3 = mock.MockObject(stableReturnValues=True)
        mockSource3._mock.setReturn('baz:source')

        sources = [mockSource1, mockSource2, mockSource3]

        mockRepos = mock.MockObject(stableReturnValues=True)
        mockRepos.getTroveInfo._mock.setReturn(sources,
            trove._TROVEINFO_TAG_SOURCENAME, nvfs)
        self.mock(helper, '_repos', mockRepos)

        expectedResult = set()
        expectedResult.add(('foo:source', mockSourceVersion, None))
        expectedResult.add(('bar:source', mockSourceVersion, None))
        expectedResult.add(('baz:source', mockSourceVersion, None))

        result = helper._getSourceTroves(trvSpec)
        self.failUnlessEqual(result, expectedResult)
        mockClient.createChangeSet._mock.assertCalled(cl, withFiles=False,
            withFileContents=False, recurse=False)
        mockGetTrove._mock.assertCalled(mockChangeSet, *trvSpec)
        mockTrove.iterTroveList._mock.assertCalled(weakRefs=True,
                                                   strongRefs=True)
        mockRepos.getTroveInfo._mock.assertCalled(
            trove._TROVEINFO_TAG_SOURCENAME, nvfs)
        mockVersion.getSourceVersion._mock.assertCalled()
        mockVersion.getSourceVersion._mock.assertCalled()
        mockVersion.getSourceVersion._mock.assertCalled()
        mockSource1._mock.assertCalled()
        mockSource2._mock.assertCalled()
        mockSource3._mock.assertCalled()

    def testGetTrove(self):
        trvSpec = self.findTroveReturn[3]
        mockTroveCs = mock.MockObject()
        mockCs = mock.MockObject(stableReturnValues=True)
        mockCs.getNewTroveVersion._mock.setReturn(mockTroveCs, *trvSpec)

        mockTrove = mock.MockObject()
        mockTroveTrove = mock.MockObject(stableReturnValues=True)
        mockTroveTrove._mock.setReturn(mockTrove, mockTroveCs,
                                       skipIntegrityChecks=True)
        self.mock(trove, 'Trove', mockTroveTrove)

        helper = conaryhelper.ConaryHelper(self.updateBotCfg)
        result = helper._getTrove(mockCs, *trvSpec)

        self.failUnless(result is mockTrove)
        mockCs.getNewTroveVersion._mock.assertCalled(*trvSpec)
        mockTroveTrove._mock.assertCalled(mockTroveCs,
                                          skipIntegrityChecks=True)


testsetup.main()
