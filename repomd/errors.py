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

'''
Errors specific to repomd module.
'''

__all__ = ('RepoMdError', 'ParseError', 'UnknownElementError')

class RepoMdError(Exception):
    '''
    Base exception for all repomd exceptions. This should never be
    expllicitly raised.
    '''

class ParseError(RepoMdError):
    '''
    Base parsing error.
    '''

class UnknownElementError(ParseError):
    '''
    Raised when unhandled elements are found in the parser.
    '''

    def __init__(self, element):
        ParseError.__init__(self)
        self._element = element
        self._error = 'Element %s is not supported by this parser.'

    def __str__(self):
        return self._error % (self._element.getAbsoluteName(), )

class UnknownAttributeError(UnknownElementError):
    '''
    Raised when unhandled attributes are found in the parser.
    '''

    def __init__(self, element, attribute):
        UnknownElementError.__init__(self, element)
        self._attribute = attribute
        self._error = ('Attribute %s of %%s is not supported by this '
                       'parser.' % (attribute, ))
