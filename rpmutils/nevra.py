#
# Copyright (c) rPath, Inc.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#


"""
Module for defining NEVRA datastructure.
"""

from collections import namedtuple

from rpmutils import rpmvercmp

class EVR(namedtuple('evr', 'epoch version release')):
    """
    Class for storing just epoch, version, and release for comparison purposes.
    """
    __slots__ = ()


class NEVRA(namedtuple('nevra', 'name epoch version release arch')):
    """
    Class to represent an RPM NEVRA.
    """

    __slots__ = ()

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

    def __lt__(self, other):
        c = self.__cmp__(other)
        if c == -1:
            return True
        return False

    @property
    def evr(self):
        return EVR(self.epoch, self.version, self.release)
