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

class _QuotedLineTokenizer(object):
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
        self._singleQuotedString = False
        self._doubleQuotedString = False

        self._list = ['']
        for char in line:
            self._cur = char
            if char in self._states:
                self._states[char]()
            else:
                self._states['other']()

        if self._list[-1] == '':
            self._list = self._list[:-1]

        return self._list

    def _space(self):
        if not self._singleQuotedString and not self._doubleQuotedString:
            self._list.append('')

    def _singleQuote(self):
        self._add()
        self._singleQuotedString = not self._singleQuotedString

    def _doubleQuote(self):
        self._add()
        self._doubleQuotedString = not self._doubleQuotedString

    def _add(self):
        self._list[-1] += self._cur


class Parser(object):
    def __init__(self):
        self._text = ''
        self._line = None
        self._curObj = None
        self._lineTokenizer = _QuotedLineTokenizer()

        self._containerClass = None
        self._states = {}

    def parse(self, fn):
        if isinstance(fn, str):
            fileObj = open(fn)
        else:
            fileObj = fn

        for line in fileObj:
            self._parseLine(line)

    def _parseLine(self, cfgline):
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
                self._text += ' '.join(self._line)

    @staticmethod
    def _getState(key):
        return key

    def _getLine(self):
        return ' '.join(self._line[1:]).strip()

    def _checkLength(self, length, gt=False):
        if gt: assert(len(self._line) > length)
        else: assert(len(self._line) == length)

    def _keyval(self):
        key = self._getState(self._line[0])
        value = ' '.join(self._line[1:]).strip()
        self._curObj.set(key, value)
