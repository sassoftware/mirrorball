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

from updatebot import advise
from updatebot import errors

class AdviseTest(slehelp.Helper):
    def testCheck(self):
        mockRpmSource = mock.MockObject()
        mockPatchSource = mock.MockObject()
        mockHasException = mock.MockObject()
        mockIsSecurity = mock.MockObject()
        mockMkAdvisory = mock.MockObject()

        mockSrcPkg1 = mock.MockObject()
        mockSrcPkg2 = mock.MockObject()
        mockSrcPkg3 = mock.MockObject()

        mockBinPkg1 = mock.MockObject()
        mockBinPkg2 = mock.MockObject()
        mockBinPkg3 = mock.MockObject()

        mockPatch1 = mock.MockObject()
        mockPatch2 = mock.MockObject()

        srcPkgMap = {mockSrcPkg1: [mockSrcPkg1, mockBinPkg1],
                     mockSrcPkg2: [mockSrcPkg2, mockBinPkg2],
                     mockSrcPkg3: [mockSrcPkg3, mockBinPkg3]}
        mockRpmSource._mock.set(srcPkgMap=srcPkgMap)

        pkgMap = {mockBinPkg1: set([mockPatch1, ]), }
        mockPatchSource._mock.set(pkgMap=pkgMap)

        input = [(None, mockSrcPkg1),
                 (None, mockSrcPkg2),
                 (None, mockSrcPkg3)]

        advisor = advise.Advisor(self.updateBotCfg, mockRpmSource,
                                 mockPatchSource)
        self.mock(advisor, '_hasException', mockHasException)
        self.mock(advisor, '_isSecurity', mockIsSecurity)
        self.mock(advisor, '_mkAdvisory', mockMkAdvisory)

        mockHasException._mock.setReturn(True, mockBinPkg2)
        mockHasException._mock.setReturn(False, mockBinPkg3)
        mockIsSecurity._mock.setReturn(False, mockBinPkg3)

        expected = {(None, mockSrcPkg1): set([mockPatch1, ]),}

        # test normal case
        result = advisor.check(input)
        self.failUnlessEqual(result, None)
        self.failUnlessEqual(advisor._cache, expected)
        mockHasException._mock.assertCalled(mockBinPkg2)
        mockHasException._mock.assertCalled(mockBinPkg3)
        mockIsSecurity._mock.assertCalled(mockBinPkg3)

        # test exception case
        mockHasException._mock.setReturn(False, mockBinPkg2)
        mockIsSecurity._mock.setReturn(True, mockBinPkg2)
        self.failUnlessRaises(errors.NoAdvisoryFoundError, advisor.check, input)
        mockHasException._mock.assertCalled(mockBinPkg2)
        mockIsSecurity._mock.assertCalled(mockBinPkg2)

    def testHasException(self):
        binPkg = mock.MockObject(stableReturnValues=True)
        mockCfg = mock.MockObject(stableReturnValues=True)
        mockCfg._mock.set(advisoryException=[['foo', None]])

        advisor = advise.Advisor(mockCfg, None, None)

        binPkg._mock.set(location='foo/bar')
        result = advisor._hasException(binPkg)
        self.failUnlessEqual(result, True)

        binPkg._mock.set(location='bar/foo')
        result = advisor._hasException(binPkg)
        self.failUnlessEqual(result, False)

    def testIsSecurity(self):
        advisor = advise.Advisor(self.updateBotCfg, None, None)
        binPkg = mock.MockObject(stableReturnValues=True)
        binPkg._mock.set(location='foo-Updates/bar')
        result = advisor._isSecurity(binPkg)
        self.failUnlessEqual(result, True)
        binPkg._mock.set(location='foo-Online/bar')
        result = advisor._isSecurity(binPkg)
        self.failUnlessEqual(result, False)

testsetup.main()
