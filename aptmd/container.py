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

class Container(object):
    __slots__ = ('_data', )

    def __init__(self):
        for cls in self.__class__.__mro__:
            if hasattr(cls, '__slots__'):
                for item in cls.__slots__:
                    print item
                    setattr(self, item, None)

        self._data = {}

    def set(self, key, value):
        if key not in self._data:
            self._data[key] = value

    __setitem__ = set

    def get(self, key):
        return self._data[key]

    __getitem__ = get

    def finalize(self):
        pass
