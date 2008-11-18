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

import email
import shutil
import mailbox
import tempfile

from aptmd.container import Container
from aptmd.parser import ContainerizedParser as Parser

class BaseContainer(Container):
    __slots__ = ('fromAddr', 'fromName', 'timestamp', 'subject', 'msg',
                 'description', 'summary', 'packages')

class BaseParser(Parser):
    def __init__(self):
        Parser.__init__(self)

        self._curMsg = None
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
        shutil.copyfileobj(fileObj, tmpfh)
        tmpfh.close()

        mbox = mailbox.mbox(tmpfn)
        return mbox

    def _parseMsg(self, msg):
        self._newContainer()
        assert msg.get_content_type() == 'text/plain'

        self._curMsg = msg
        self._curObj.msg = msg

        # Extract info from message
        fromLine = msg['From']
        self._curObj.fromAddr = fromLine[:fromLine.find('(')].replace(' at ', '@')
        self._curObj.fromName = fromLine[fromLine.find('('):].strip('()')
        self._curObj.timestamp = ' '.join(msg.get_from().split()[4:])
        self._curObj.subject = msg['Subject'].replace('\n\t', ' ')

        for line in msg.get_payload().split('\n'):
            self._parseLine(line)

        # Make sure last object gets added to self._objects while allowing
        # subclasses to have special handling in newContainer.
        self._newContainer()
