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
from testrunner import resources

import os
import StringIO

from aptmd import packages

import slehelp

class PackagesTest(slehelp.Helper):
    def testMetadataParse1(self):
        ctrlFile = os.path.join(resources.archivePath, 'control-files',
            'ascii.control')

        parser = packages.PackagesParser()
        parser.parse(ctrlFile)
        self.failUnlessEqual(parser._curObj.name, 'ascii')
        self.failUnlessEqual(parser._curObj.version, '3.8')
        self.failUnlessEqual(parser._curObj.release, '2')
        self.failUnlessEqual(parser._curObj.arch, 'i386')
        self.failUnlessEqual(parser._curObj.get('installed-size'), '72')
        self.failUnlessEqual(parser._curObj.summary, 'interactive ASCII name and synonym chart')
        self.failUnlessEqual(parser._curObj.description, """\
 The ascii utility provides easy conversion between various byte representations
 and the American Standard Code for Information Interchange (ASCII) character
 table.  It knows about a wide variety of hex, binary, octal, Teletype mnemonic,
 ISO/ECMA code point, slang names, XML entity names, and other representations.
 Given any one on the command line, it will try to display all others.  Called
 with no arguments it displays a handy small ASCII chart.
 .
 Homepage: http://www.catb.org/~esr/ascii/
""")

testsetup.main()
