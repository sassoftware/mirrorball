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
