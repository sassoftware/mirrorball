#!/usr/bin/python
#
# Copyright (c) SAS Institute, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#


"""
Module for testing the renaming of packages.

The goal here is to have code that can be pasted into dep-import.recipe to
collapse package names.
"""

class Recipe(object):
    def __init__(r):
        r.name = None
        r.fileNames = []
        r.finalNames = set()
        r.suffixes = ('-base', '-bin', '-data', '-dev', '-doc', '-dbg', '-pic',
                      '-runtime')

    def filterSuffix(r, pkg):
        for suffix in r.suffixes:
            if pkg.endswith(suffix):
                return pkg[:-len(suffix)]
        return pkg

    def unpack(r):
        for n in r.fileNames:
            # collapse common suffixes
            n = r.filterSuffix(n)

            # collapse libfoo.* -> foo if foo is the base package
            if (not r.name.startswith('lib')
                and n.startswith('lib')
                and n[3:].startswith(r.name)):

                n = r.name

            # collapse libfoo.* -> libfoo when base package is libfoo
            elif (r.name.startswith('lib')
                  and n.startswith(r.name)):

                n = r.name

            # collapse foo123 -> foo when foo is the base package
            elif (n.startswith(r.name)
                  and n[len(r.name):].isdigit()):

                n = r.name

            # collapse foo1[a-z]* when foo is the base package
            elif (n.startswith(r.name)
                  and len(n) > len(r.name)
                  and n[len(r.name):len(r.name)+1].isdigit()
                  and n[len(r.name)+1:].isalpha()):

                n = r.name

            # collapse foo1 -> foo if foo exists
            elif n[-1].isdigit():
                # find all package names with suffixes trimmed
                prefixes = [ r.filterSuffix(x) for x in r.fileNames
                             if n.startswith(r.filterSuffix(x)) ]

                # unique the list
                prefixes = list(set(prefixes))

                # remove the current package name
                if n in prefixes: prefixes.remove(n)

                # If there is only one choice left and the current name starts
                # with the only choice it must be correct.
                if len(prefixes) == 1 and n.startswith(prefixes[0]):
                    n = prefixes[0]


            # handle case where base package is foo123 but sub package is foo
            # libfoo -> foo123 and foo -> foo123 if foo123 is the base package
            if (r.name[-1].isdigit()
                and (r.name.startswith(n)
                     or (n.startswith('lib')
                         and r.name.startswith(n[3:]))
                    )
               ):

                n = r.name

            r.finalNames.add(n)


if __name__ == '__main__':
    def test(name, inFiles, outFiles):
        obj = Recipe()
        obj.name = name
        obj.fileNames = inFiles
        obj.unpack()

        if obj.finalNames != outFiles:
            print "expected: %s" % outFiles
            print "actual: %s" % obj.finalNames

        assert obj.finalNames == outFiles

    test('lzma',
        ['lzma-dev', 'lzma', 'lzma-dev', 'lzma'],
        set(['lzma']))

    test('libidn',
        ['libidn11', 'libidn11-dev', 'libidn11', 'libidn11-dev'],
        set(['libidn']))

    test('wireless-tools',
        ['libiw-dev', 'wireless-tools', 'libiw29', 'libiw-dev',
         'wireless-tools', 'libiw29'],
        set(['wireless-tools', 'libiw']))

    test('newt',
        ['libnewt0.52', 'python-newt-dbg', 'whiptail', 'libnewt-pic',
         'libnewt-dev', 'python-newt', 'libnewt-pic', 'python-newt',
         'whiptail', 'libnewt-dev', 'libnewt0.52', 'python-newt-dbg'],
        set(['newt', 'python-newt', 'whiptail']))

    test('libsepol',
        ['libsepol1-dev', 'libsepol1', 'libsepol1-dbg', 'sepol-utils',
         'sepol-utils-dbg', 'sepol-utils', 'libsepol1', 'libsepol1-dev',
         'libsepol1-dbg', 'sepol-utils-dbg'],
        set(['libsepol', 'sepol-utils']))

    test('libedit',
        ['libedit-dev', 'libedit2', 'libedit-dev', 'libedit2'],
        set(['libedit']))

    test('keyutils',
        ['libkeyutils1', 'libkeyutils-dev', 'libkeyutils1', 'libkeyutils-dev'],
        set(['keyutils']))

    test('krb5',
        ['krb5-doc', 'libkrb5-dbg', 'libkadm55', 'libkrb5-dev', 'libkrb53',
         'krb5-user', 'libkadm55', 'libkrb5-dbg', 'krb5-user', 'libkrb53',
         'libkrb5-dev'],
        set(['krb5', 'libkadm55', 'krb5-user']))

    test('libtasn1-3',
        ['libtasn1-3-dbg', 'libtasn1-3-dev', 'libtasn1-3', 'libtasn1-3-dev',
         'libtasn1-3-dbg', 'libtasn1-3'],
        set(['libtasn1-3']))

    test('libgpg-error',
        ['libgpg-error0', 'libgpg-error-dev', 'libgpg-error-dev',
         'libgpg-error0'],
        set(['libgpg-error']))

    test('pam',
        ['libpam-doc', 'libpam-runtime', 'libpam-cracklib', 'libpam-modules',
         'libpam0g', 'libpam0g-dev', 'libpam0g', 'libpam-cracklib',
         'libpam0g-dev', 'libpam-modules'],
        set(['pam']))

    test('libusb',
        ['libusb-0.1-4', 'libusb++-dev', 'libusb++-0.1-4c2', 'libusb-dev',
         'libusb++-0.1-4c2', 'libusb++-dev', 'libusb-0.1-4', 'libusb-dev'],
        set(['libusb']))

    test('ncurses',
        ['ncurses-base', 'ncurses-term', 'libncurses5-dbg', 'lib32ncurses5',
         'ncurses-bin', 'libncursesw5-dbg', 'libncursesw5', 'libncurses5-dev',
         'libncurses5', 'lib32ncurses5-dev', 'libncursesw5-dev',
         'libncursesw5-dbg', 'libncurses5-dev', 'lib64ncurses5',
         'libncursesw5-dev', 'libncursesw5', 'libncurses5',
         'lib64ncurses5-dev', 'libncurses5-dbg', 'ncurses-bin'],
        set(['ncurses', 'ncurses-term', 'lib32ncurses5', 'lib64ncurses5']))

    test('openssl',
        ['openssl-doc', 'openssl', 'libssl0.9.8-dbg', 'libssl-dev',
         'libssl0.9.8', 'libssl0.9.8-dbg', 'libssl0.9.8', 'openssl',
         'libssl-dev'],
        set(['openssl', 'libssl']))

    test('sqlite3',
        ['sqlite3-doc', 'libsqlite3-dev', 'libsqlite3-0', 'sqlite3', 'sqlite3',
         'libsqlite3-0', 'libsqlite3-dev'],
        set(['sqlite3']))

    test('gnutls13',
        ['gnutls-doc', 'libgnutlsxx13', 'libgnutls13', 'libgnutls13-dbg',
         'libgnutls-dev', 'libgnutlsxx13', 'libgnutls13-dbg', 'libgnutls-dev',
         'libgnutls13'],
        set(['gnutls13']))

    test('bzip2',
        ['bzip2-doc', 'libbz2-1.0', 'bzip2', 'libbz2-dev', 'lib32bz2-1.0',
         'lib32bz2-dev', 'libbz2-dev', 'libbz2-1.0', 'bzip2', 'lib64bz2-1.0',
         'lib64bz2-dev'],
        set(['bzip2', 'libbz2', 'lib32bz2', 'lib64bz2']))

    test('zlib',
         ['zlib1g-dev', 'lib32z1-dev', 'lib32z1', 'zlib1g-dbg', 'zlib1g',
          'lib64z1-dev', 'zlib1g-dbg', 'zlib1g', 'zlib1g-dev', 'lib64z1'],
         set(['zlib', 'lib32z1', 'lib64z1']))
