#
# Copyright (c) 2008-2009 rPath, Inc.
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
