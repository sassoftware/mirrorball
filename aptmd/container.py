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
Base container class to be used with a ContainerizedParser.
"""

class Container(object):
    """
    Base container class.
    """

    _slots = ('_data', )

    def __init__(self):
        # W0212 - Access to a protected member _slots of a client class
        # pylint: disable-msg=W0212

        for cls in self.__class__.__mro__:
            if hasattr(cls, '_slots'):
                for item in cls._slots:
                    setattr(self, item, None)

        self._data = {}

    def __eq__(self, other):
        """
        Check for equality.
        """

        if not isinstance(other, Container):
            return False
        return cmp(self, other) == 0

    def set(self, key, value):
        """
        Set data in a local dictionary, also used for __setitem__.
        @param key - key for dictionary
        @type key hashable object
        @param value - value for dictionary
        @type value object
        """

        if key not in self._data:
            self._data[key] = value

    __setitem__ = set

    def get(self, key):
        """
        Get information from the data dict.
        @param key - item to retrieve from the dict
        @type key hashable object
        """

        return self._data[key]

    __getitem__ = get

    def finalize(self):
        """
        Method to be implemented by subclasses for computing any data based
        on parsed information.
        """
