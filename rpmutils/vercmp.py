#
# Copyright (c) 2008-2009 rPath, Inc.
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

"""
Module that implements rpm version comparison.
"""

def _rpmversplit(s):
    """
    Split version strings.
    """

    l = []
    isNumericHunk = s[0].isdigit()

    i = 1
    start = 0


    while i < len(s):
        if not s[i].isalnum():
            l.append(s[start:i])
            start = i + 1
        elif isNumericHunk != s[i].isdigit():
            l.append(s[start:i])
            start = i

        i += 1

    l.append(s[start:i])

    # filter out empty strings
    return [ x for x in l if x ]

def rpmvercmp(ver1string, ver2string):
    """
    Compare rpm version strings.
    """

    # R0911 - Too many return statements
    # pylint: disable-msg=R0911

    ver1list = _rpmversplit(ver1string)
    ver2list = _rpmversplit(ver2string)

    while ver1list or ver2list:
        if not ver1list:
            return -1
        elif not ver2list:
            return 1

        v1 = ver1list.pop(0)
        v2 = ver2list.pop(0)

        if v1.isdigit() and v2.isdigit():
            v1 = int(v1)
            v2 = int(v2)
        elif v1.isdigit() and not v2.isdigit():
            # numbers are newer than letters
            return 1
        elif not v1.isdigit() and v2.isdigit():
            return -1

        if v1 < v2:
            return -1
        elif v1 > v2:
            return 1

    return 0
