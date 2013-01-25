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
