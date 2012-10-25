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
Errors specific to repomd module.
"""

__all__ = ('RepoMdError', 'ParseError', 'UnknownElementError')

class RepoMdError(Exception):
    """
    Base exception for all repomd exceptions. This should never be
    expllicitly raised.
    """

class ParseError(RepoMdError):
    """
    Base parsing error.
    """

class UnknownElementError(ParseError):
    """
    Raised when unhandled elements are found in the parser.
    """

    def __init__(self, element):
        ParseError.__init__(self)
        self._element = element
        self._error = 'Element %s is not supported by this parser.'

    def __str__(self):
        return self._error % (self._element.getAbsoluteName(), )

class UnknownAttributeError(UnknownElementError):
    """
    Raised when unhandled attributes are found in the parser.
    """

    def __init__(self, element, attribute):
        UnknownElementError.__init__(self, element)
        self._attribute = attribute
        self._error = ('Attribute %s of %%s is not supported by this '
                       'parser.' % (attribute, ))
