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
Common module for apt metadata parsers to inherit from.
"""

from updatebot.lib import util

from aptmd.container import Container
from aptmd.parser import ContainerizedParser as Parser

class BaseContainer(Container):
    """
    Base class that implements a data container for entries in apt repository
    metadata.
    """

    _slots = ('name', 'arch', 'epoch', 'version', 'release', 'mdpath',
        'orignalmaintainer')

    def __repr__(self):
        # Instance of 'BaseContainer' has no 'name' member
        # pylint: disable-msg=E1101

        klass = self.__class__.__name__.strip('_')
        return '<%s(%s, %s, %s, %s, %s)>' % (klass, self.name, self.epoch,
                                             self.version, self.release,
                                             self.arch)

    def __hash__(self):
        # Instance of 'BaseContainer' has no 'name' member
        # pylint: disable-msg=E1101

        return hash((self.name, self.epoch, self.version, self.release,
                     self.arch))

    def __cmp__(self, other):
        return util.packageCompare(self, other)


class BaseParser(Parser):
    """
    Base parser class to be used in parsing apt metadata.
    """

    def __init__(self):
        Parser.__init__(self)

        self._containerClass = BaseContainer
        self._mdPath = None

        self._bucketState = None

        self._states.update({
            'package'               : self._package,
            'architecture'          : self._architecture,
            'version'               : self._version,
            'priority'              : self._keyval,
            'section'               : self._keyval,
            'maintainer'            : self._keyval,
            '_maintainer'           : self._maintainer,
            'original-maintainer'   : self._originalmaintainer,
            ''                      : self._linewrap,
        })

    def parse(self, fn, path):
        """
        Parse repository metadata.
        """

        self._mdPath = path
        return Parser.parse(self, fn)

    def _newContainer(self):
        """
        Create a new container object and store the finished one.
        """

        self._bucketState = None
        if self._curObj is not None:
            self._curObj.mdpath = self._mdPath
        return Parser._newContainer(self)

    def _package(self):
        """
        Parse package info.
        """

        self._newContainer()
        self._curObj.name = self._getLine()

    def _architecture(self):
        """
        Parse architectures.
        """

        # Attribute 'arch' defined outside __init__
        # pylint: disable-msg=W0201

        arch = self._getLine()
        assert arch in ('all', 'i386', 'amd64')
        self._curObj.arch = arch

    def _version(self):
        """
        Parse versions.
        """

        # Attribute 'release' defined outside __init__
        # pylint: disable-msg=W0201

        debVer = self._getLine()

        epoch = '0'
        if ':' in debVer:
            epoch = debVer.split(':')[0]
            debVer = ':'.join(debVer.split(':')[1:])


        if '-' in debVer:
            sdebVer = debVer.split('-')
            version = sdebVer[0]
            release = '-'.join(sdebVer[1:])
        else:
            version = debVer
            release = '0'

        self._curObj.epoch = epoch
        self._curObj.version = version
        self._curObj.release = release

    def _originalmaintainer(self):
        """
        Parse orignal maintainer info.
        """

        self._curObj.orignalmaintainer = []
        self._bucketState = '_maintainer'
        self._maintainer()

    def _maintainer(self):
        """
        Parse mainter.
        """

        data = ' '.join(self._line[1:])
        if ',' in data:
            lst = data.split(',')
        else:
            lst = [ data ]

        self._curObj.orignalmaintainer.extend(lst)

    def _linewrap(self):
        """
        Handle multiline sections.
        """

        if self._bucketState is None:
            return

        state = self._getState(self._bucketState)
        func = self._states[state]
        func()
