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
Common parser module for parsing mbox mail archives.
"""

import shutil
import mailbox
import tempfile

from aptmd.container import Container
from aptmd.parser import ContainerizedParser as Parser

class BaseContainer(Container):
    """
    Base MBox Message container class.
    """

    _slots = ('fromAddr', 'fromName', 'timestamp', 'subject', 'msg',
              'description', 'summary', 'packages')

    def __repr__(self):
        return self.subject


class BaseParser(Parser):
    """
    Base MBox parsing class.
    """

    def __init__(self):
        Parser.__init__(self)

        self._curMsg = None
        self._containerClass = BaseContainer
        self._states.update({
        })

    def parse(self, fileObj):
        """
        Parse file or file like objects.
        """

        self._objects = []
        mbox = self._getMbox(fileObj)
        for msg in mbox:
            self._parseMsg(msg)

        # Make sure last object gets added to self._objects while allowing
        # subclasses to have special handling in newContainer.
        self._newContainer()

        return self._objects

    @staticmethod
    def _getMbox(fileObj):
        """
        Copy a file and return a mbox instance.
        """

        tmpfn = tempfile.mktemp()
        tmpfh = open(tmpfn, 'w')
        shutil.copyfileobj(fileObj, tmpfh)
        tmpfh.close()

        mbox = mailbox.mbox(tmpfn)
        return mbox

    def _parseMsg(self, msg):
        """
        Parse a single message.
        """

        self._newContainer()
        assert msg.get_content_type() == 'text/plain'

        # W0201: Attribute 'msg' defined outside __init__
        # W0201: Attribute 'fromAddr' defined outside __init__
        # W0201: Attribute 'subject' defined outside __init__
        # W0201: Attribute 'timestamp' defined outside __init__
        # W0201: Attribute 'fromName' defined outside __init__
        # pylint: disable-msg=W0201

        self._curMsg = msg
        self._curObj.msg = msg

        # Extract info from message
        fromLine = msg['From']
        self._curObj.fromAddr = \
                fromLine[:fromLine.find('(')].replace(' at ', '@')
        self._curObj.fromName = fromLine[fromLine.find('('):].strip('()')
        self._curObj.timestamp = ' '.join(msg.get_from().split()[4:])
        self._curObj.subject = msg['Subject'].replace('\n\t', ' ')

        for line in msg.get_payload().split('\n'):
            self._parseLine(line)
