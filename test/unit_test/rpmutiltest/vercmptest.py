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

from rpmutils import rpmvercmp

class VerCmpTest(slehelp.Helper):
    def testVerCmp(self):
        def _test(a, b, expected):
            result = rpmvercmp(a, b)
            self.failUnlessEqual(result, expected)

        _test('1', '1', 0)
        _test('1', '2', -1)
        _test('2', '1', 1)
        _test('a', 'a', 0)
        _test('a', 'b', -1)
        _test('b', 'a', 1)
        _test('1.2', '1.3', -1)
        _test('1.3', '1.1', 1)
        _test('1.a', '1.a', 0)
        _test('1.a', '1.b', -1)
        _test('1.b', '1.a', 1)
        _test('1.2+', '1.2', 0)
        _test('1.0010', '1.0', 1)
        _test('1.05', '1.5', 0)
        _test('1.0', '1', 1)
        _test('2.50', '2.5', 1)
        _test('fc4', 'fc.4', 0)
        _test('FC5', 'fc5', -1)
        _test('2a', '2.0', -1)
        _test('1.0', '1.fc4', 1)
        _test('3.0.0_fc', '3.0.0.fc', 0)
        _test('1++', '1_', 0)
        _test('+', '_', -1)
        _test('_', '+', 1)

testsetup.main()
