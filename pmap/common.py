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

from aptmd.container import Container
from aptmd.parser import ContainerizedParser as Parser

class BaseContainer(Container):
    pass

class BaseParser(Parser):
    def __init__(self):
        Parser.__init__(self)

        self._containerClass = BaseContainer
        self._objects = []

        self._states.update({
            '--------------'            : self._messagesep,
        })

    def _messagesep(self):
        if self._line[1] == 'next' and self._line[2] == 'part':
            if self._curObj is not None:
                if hasattr(self._curObj, 'finalize'):
                    self._curObj.finalize()
                self._objects.append(self._curObj)
            self._curObj = self._containerClass()
