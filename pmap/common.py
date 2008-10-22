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

import tempfile

from upstream import mailbox

from aptmd.container import Container
from aptmd.parser import ContainerizedParser as Parser

class BaseContainer(Container):
    __slots__ = ('fromAddr', 'fromName', 'timestamp')

class BaseParser(Parser):
    def __init__(self):
        Parser.__init__(self)

        self._containerClass = BaseContainer
        self._states.update({
        })

    def parse(self, fileObj):
        self._objects = []
        mbox = self._getMbox(fileObj)
        for msg in mbox:
            self._parseMsg(msg)
        return self._objects

    def _getMbox(self, fileObj):
        tmpfn = tempfile.mktemp()
        tmpfh = open(tmpfn, 'w')
        tmpfh.write(fileObj.read())
        tmpfh.close()

        mbox = mailbox.mbox(tmpfn)
        return mbox

    def _parseMsg(self, msg):
        self._newContainer()

