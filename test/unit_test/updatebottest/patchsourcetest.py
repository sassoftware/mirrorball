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

from updatebot import patchsource

class PatchSourceTest(slehelp.Helper):
    def testLoadFromClient(self):
        mockPatch = mock.MockObject()
        mockClient = mock.MockObject(stableReturnValues=True)
        mockClient.getPatchDetail._mock.setReturn([mockPatch, ])

        mockLoadOne = mock.MockObject(stableReturnValues=True)
        mockLoadOne._mock.setReturn(None, mockPatch, '/foo')

        patchSource = patchsource.PatchSource()
        self.mock(patchSource, '_loadOne', mockLoadOne)

        result = patchSource.loadFromClient(mockClient, '/foo')
        self.failUnlessEqual(result, None)
        mockClient.getPatchDetail._mock.assertCalled()
        mockLoadOne._mock.assertCalled(mockPatch, '/foo')

    def testLoadOne(self):
        mockPackage = mock.MockObject(stableReturnValues=True)
        mockPackage._mock.set(location='foo/bar')

        mockPatch = mock.MockObject(stableReturnValues=True)
        mockPatch._mock.set(packages=[mockPackage, ])

        expectedResult = {mockPackage: set([mockPatch, ])}

        patchSource = patchsource.PatchSource()
        result = patchSource._loadOne(mockPatch, 'baz')
        self.failUnlessEqual(result, None)
        self.failUnlessEqual(patchSource.pkgMap, expectedResult)
        self.failUnlessEqual(mockPackage.location, 'baz/foo/bar')


testsetup.main()
