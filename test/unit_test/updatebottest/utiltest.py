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

from updatebot import util

class UtilTest(slehelp.Helper):
    def testJoin(self):
        def t(input, output):
            result = util.join(*input)
            self.failUnlessEqual(result, output)

        t(['/foo', 'bar'],
          '/foo/bar')
        t(['/foo/../', 'bar/'],
          '/bar')
        t(['/foo', '/bar'],
          '/foo/bar')

    def testSrpmToConaryVersion(self):
        mockSrcPkg = mock.MockObject()

        mockSrcPkg._mock.set(version='a-b')
        mockSrcPkg._mock.set(release='b-c')

        expected = 'a_b_b_c'
        result = util.srpmToConaryVersion(mockSrcPkg)
        self.failUnlessEqual(result, expected)

        mockSrcPkg._mock.set(version='a_b')
        result = util.srpmToConaryVersion(mockSrcPkg)
        self.failUnlessEqual(result, expected)

    def testPackagevercmp(self):
        def t(expected, kw1, kw2):
            mockPkg1 = mock.MockObject()
            mockPkg2 = mock.MockObject()

            for kw in kw1.iterkeys():
                mockPkg1._mock.set(**{kw:kw1[kw]})
            for kw in kw2.iterkeys():
                mockPkg2._mock.set(**{kw:kw2[kw]})

            result = util.packagevercmp(mockPkg1, mockPkg2)
            self.failUnlessEqual(result, expected)

        t(1, {'epoch': '1'},
             {'epoch': '0'})
        t(-1, {'epoch': '0'},
              {'epoch': '1'})
        t(1, {'epoch': '0',
              'version': '1'},
             {'epoch': '0',
              'version': '0'})
        t(-1, {'epoch': '0',
              'version': '0'},
             {'epoch': '0',
              'version': '1'})
        t(1, {'epoch': '0',
              'version': '0',
              'release': '1'},
             {'epoch': '0',
              'version': '0',
              'release': '0'})
        t(-1, {'epoch': '0',
              'version': '0',
              'release': '0'},
             {'epoch': '0',
              'version': '0',
              'release': '1'})
        t(0, {'epoch': '0',
              'version': '0',
              'release': '0'},
             {'epoch': '0',
              'version': '0',
              'release': '0'})


testsetup.main()
