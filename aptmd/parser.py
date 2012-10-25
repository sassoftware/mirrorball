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
Base parsing module, defines all low level parser classes.
"""

import re

class _QuotedLineTokenizer(object):
    """
    Class for breaking up a line into quoted chunks.
    """

    def __init__(self):
        self._cur = None
        self._list = None
        self._singleQuotedString = False
        self._doubleQuotedString = False
        self._states = {' ': self._space,
                        '\'': self._singleQuote,
                        '"': self._doubleQuote,
                        'other': self._add,
                       }

    def tokenize(self, line):
        """
        Break apart the line based on quotes.
        @param line: line from a file.
        @type line string
        """

        self._singleQuotedString = False
        self._doubleQuotedString = False

        self._list = [[]]
        for char in line:
            self._cur = char
            if char in self._states:
                self._states[char]()
            else:
                self._states['other']()

        if not self._list[-1]:
            del self._list[-1]

        return [ ''.join(x) for x in self._list ]

    def _space(self):
        """
        Handle spaces.
        """

        if not self._singleQuotedString and not self._doubleQuotedString:
            self._list.append([])

    def _singleQuote(self):
        """
        Handle single quotes.
        """

        self._add()
        self._singleQuotedString = not self._singleQuotedString

    def _doubleQuote(self):
        """
        Handle double quotes.
        """

        self._add()
        self._doubleQuotedString = not self._doubleQuotedString

    def _add(self):
        """
        Handle all other text.
        """

        self._list[-1].append(self._cur)


class Parser(object):
    """
    Base parser class.
    """

    def __init__(self):
        self._text = ''
        self._line = None
        self._curObj = None
        self._lineTokenizer = _QuotedLineTokenizer()

        self._states = {}

    def parse(self, fn):
        """
        Parse file or file line object.
        @param fn: name of file or file like object to parse.
        @type fn: string or file like object.
        """

        if isinstance(fn, str):
            fileObj = open(fn)
        else:
            fileObj = fn

        for line in fileObj:
            self._parseLine(line)

    def _parseLine(self, cfgline):
        """
        Process a single line.
        @param cfgline: single line of text config file.
        @type cfgline: string
        """

        self._line = self._lineTokenizer.tokenize(cfgline)
        if len(self._line) > 0:
            state = self._getState(self._line[0])
            if state in self._states:
                func = self._states[state]
                if func is None:
                    # ignore this line
                    return
                func()
                self._text = ''
            else:
                self._text += '\n' + ' '.join(self._line)
        else:
            self._text += '\n'

    def _getState(self, key):
        """
        Translate the first word of a line to a key of the state dict. This
        method is meant to be overridden by subclasses.
        """

        # Method could be a function
        # pylint: disable-msg=R0201

        return key

    def _getLine(self):
        """
        Get the original line after the first word.
        """

        return ' '.join(self._line[1:]).strip()

    def _getFullLine(self):
        """
        Get the entire line including the first word.
        """

        return ' '.join(self._line).strip()

    def _checkLength(self, length, gt=False):
        """
        Validate the length of a line.
        """

        if gt:
            assert(len(self._line) > length)
        else:
            assert(len(self._line) == length)

    def _keyval(self):
        """
        Parse a line as a key/value pair.
        """

        key = self._getState(self._line[0])
        value = ' '.join(self._line[1:]).strip()
        self._curObj.set(key, value)


class ContainerizedParser(Parser):
    """
    Parser for files that can be split into containers. Generates a list of
    container objects.
    """

    def __init__(self):
        Parser.__init__(self)

        self._objects = []
        self._containerClass = None
        self._stateFilters = {
        }
        self._stateLineFilters = {
        }

    def _filter(self, fltr, state):
        """
        Build a state based on a filter.
        """

        self._stateFilters[re.compile(fltr)] = state

    def _filterLine(self, fltr, state):
        """
        Build a state based on line filter.
        """

        self._stateLineFilters[re.compile(fltr)] = state

    def _getState(self, key):
        """
        Filter states based on filter map.
        """

        key = key.strip()
        key = key.lower()
        if key.endswith(':'):
            key = key[:-1]

        if key in self._states:
            return key

        for fltr, state in self._stateFilters.iteritems():
            if fltr.match(key):
                return state

        for fltr, state in self._stateLineFilters.iteritems():
            if fltr.match(self._getFullLine()):
                return state

        return key

    def _newContainer(self):
        """
        Create a new container object and store the current one.
        """

        # self._containerClass is not callable
        # pylint: disable-msg=E1102

        if self._curObj is not None:
            if hasattr(self._curObj, 'finalize'):
                self._curObj.finalize()
            self._objects.append(self._curObj)
        self._curObj = self._containerClass()

    def parse(self, fileObj):
        """
        Parse a file or file line object.
        """

        self._objects = []
        Parser.parse(self, fileObj)
        return self._objects
