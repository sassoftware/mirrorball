#
# Copyright (c) 2011 rPath, Inc.
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
Module for defining NEVRA datastructure.
"""

from collections import namedtuple

from rpmutils import rpmvercmp

class NEVRA(namedtuple('nevra', 'name epoch version release arch')):
    """
    Class to represent an RPM NEVRA.
    """

    def __cmp__(self, other):
        if isinstance(other, tuple):
            other = self.__class__(*other)

        nameCmp = cmp(self.name, other.name)
        if nameCmp != 0:
            return nameCmp

        epochCmp = rpmvercmp(self.epoch, other.epoch)
        if epochCmp != 0:
            return epochCmp

        versionCmp = rpmvercmp(self.version, other.version)
        if versionCmp != 0:
            return versionCmp

        releaseCmp = rpmvercmp(self.release, other.release)
        if releaseCmp != 0:
            return releaseCmp

        archCmp = cmp(self.arch, other.arch)
        if archCmp != 0:
            return archCmp

        return 0

