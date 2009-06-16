#
# Copyright (c) 2009 rPath, Inc.
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
Module for parsing SuSE update info metadata. This was introduced in SLES 11.
Refer to patchxml.py for previous versions.
"""

__all__ = ('UpdateInfoXml', )

from rpath_common.xmllib import api1 as xmllib

from repomd.packagexml import PackageCompare
from repomd.xmlcommon import XmlFileParser, SlotNode
from repomd.errors import UnknownElementError, UnknownAttributeError

class _Updates(SlotNode):
    """
    Represents updates in an updateinfo.xml.
    """

    def addChild(self, child):
        """
        Set attributes on child nodes.
        """

        if child.getName() != 'update':
            raise UnknownElement(child)

        child.status = None
        child.emailfrom = None
        child.type = None

        for attr, value in child.iterAttributes():
            if attr == 'status':
                child.status = value
            elif attr == 'from':
                child.emailfrom = value
            elif attr == 'type':
                child.type = value
            elif attr == 'version':
                pass
            else:
                raise UnknownAttributeError(child, attr)

        xmllib.BaseNode.addChild(self, child)

    def getUpdateInfo(self):
        """
        Return a list of update objects.
        """

        return self.getChildren('update')


class _Update(SlotNode):
    """
    Represents an update entry in updateinfo.xml.
    """

    __slots__ = ('status', 'emailfrom', 'type', 'id', 'title', 'release',
        'issued', 'references', 'description', 'pkglist', 'packages')

    # All attributes are defined in __init__ by iterating over __slots__,
    # this confuses pylint.
    # W0201 - Attribute $foo defined outside __init__
    # pylint: disable-msg=W0201

    def addChild(self, child):
        """
        Parse the children of update.
        """

        n = child.getName()
        if n == 'id':
            self.id = child.finalize()
        elif n == 'title':
            self.title = child.finalize()
        elif n == 'release':
            self.release = child.finalize()
        elif n == 'issued':
            self.issued = child.getAttribute('date')
        elif n == 'references':
            self.references = child.getChildren('reference')
        elif n == 'description':
            self.description = child.finalize()
        elif n == 'pkglist':
            c = child.getChildren('collection')
            assert len(c) == 1
            self.pkglist = c[0].getChildren('package')
        else:
            raise UnknownElementError(child)


class _References(SlotNode):
    """
    Represent a list of references in updateinfo.xml.
    """

    def addChild(self, child):
        if child.getName() != 'reference':
            raise UnknownElementError(child)

        child.href = None
        child.id = None
        child.title = None
        child.type = None

        for attr, value in child.iterAttributes():
            if attr == 'href':
                child.href = value
            elif attr == 'id':
                child.id = value
            elif attr == 'title':
                child.title = value
            elif attr == 'type':
                child.type = value
            else:
                raise UnknownAttributeError(child, attr)

        xmllib.BaseNode.addChild(self, child)


class _Collection(SlotNode):
    """
    Represents a pkglist collection in updateinfo.xml.
    """

    def addChild(self, child):
        """
        Update child attributes.
        """

        if child.getName() != 'package':
            raise UnknownElement(child)

        child.name = None
        child.arch = None
        child.version = None
        child.release = None

        child.location = ''

        for attr, value in child.iterAttributes():
            if attr == 'name':
                child.name = value
            elif attr == 'arch':
                child.arch = value
            elif attr == 'version':
                child.version = value
            elif attr == 'release':
                child.release = value
            else:
                raise UnknownAttributeError(child, attr)

        xmllib.BaseNode.addChild(self, child)


class _UpdateInfoPackage(SlotNode, PackageCompare):
    """
    Represnts a package entry in a pkglist of an update in updateinfo.xml.
    """

    __slots__ = ('filename', 'name', 'arch', 'version', 'release',
        'reboot_suggested', 'restart_suggested',  'epoch', 'location',
        'summary', 'relogin_suggested')

    # All attributes are defined in __init__ by iterating over __slots__,
    # this confuses pylint.
    # W0201 - Attribute $foo defined outside __init__
    # pylint: disable-msg=W0201

    def addChild(self, child):
        """
        Parse children of pkglist.collection
        """

        n = child.getName()
        if n == 'filename':
            self.filename = child.finalize()
        elif n == 'reboot_suggested':
            self.reboot_suggested = child.finalize()
        elif n == 'restart_suggested':
            self.restart_suggested = child.finalize()
        elif n == 'relogin_suggested':
            self.relogin_suggested = child.finalize()
        else:
            raise UnknownElementError(child)


class UpdateInfoXml(XmlFileParser):
    """
    Bind all types for parsing updateinfo.xml.
    """

    def _registerTypes(self):
        """
        Setup parser.
        """

        self._databinder.registerType(_Updates, name='updates')
        self._databinder.registerType(_Update, name='update')
        self._databinder.registerType(_References, name='references')
        self._databinder.registerType(_Collection, name='collection')
        self._databinder.registerType(_UpdateInfoPackage, name='package')

        self._databinder.registerType(xmllib.StringNode, name='id')
        self._databinder.registerType(xmllib.StringNode, name='title')
        self._databinder.registerType(xmllib.StringNode, name='release')
        self._databinder.registerType(xmllib.StringNode, name='description')
        self._databinder.registerType(xmllib.StringNode, name='filename')
