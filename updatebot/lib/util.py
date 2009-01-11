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
Module for common utility functions.
"""

# W0611 - Unused import rmtree
# pylint: disable-msg=W0611

import os
from conary.lib.util import rmtree

from rpmutils import rpmvercmp

def join(a, *b):
    """
    Version of os.path.join that doesn't reroot when it finds a leading /.
    """

    root = os.path.normpath(a)
    if root == '/':
        root = ''
    for path in b:
        root += os.sep + os.path.normpath(path)
    return os.path.abspath(root)

def srpmToConaryVersion(srcPkg):
    """
    Get the equvialent conary version from a srcPkg object.
    @param srcPkg: package object for a srpm
    @type srcPkg: repomd.packagexml._Package
    @return conary trailing version
    """

    version = srcPkg.version.replace('-', '_')
    release = srcPkg.release.replace('-', '_')
    cnyver = '_'.join([version, release])
    return cnyver

def packagevercmp(a, b):
    """
    Compare two package objects.
    @param a: package object from repo metadata
    @type a: repomd.packagexml._Package
    @param b: package object from repo metadata
    @type b: repomd.packagexml._Package
    """

    epochcmp = rpmvercmp(a.epoch, b.epoch)
    if epochcmp != 0:
        return epochcmp

    vercmp = rpmvercmp(a.version, b.version)
    if vercmp != 0:
        return vercmp

    relcmp = rpmvercmp(a.release, b.release)
    if relcmp != 0:
        return relcmp

    return 0

def packageCompare(a, b):
    """
    Compare package with arch.
    """

    pkgvercmp = packagevercmp(a, b)
    if pkgvercmp != 0:
        return pkgvercmp

    archcmp = cmp(a.arch, b.arch)
    if archcmp != 0:
        return archcmp

    return 0

def packageCompareByName(a, b):
    """
    Compare packages by name and the follow packagevercmp.
    """

    nameCmp = cmp(a.name, b.name)
    if nameCmp != 0:
        return nameCmp

    return packagevercmp(a, b)
