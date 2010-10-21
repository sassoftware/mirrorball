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

import os

import logging

log = logging.getLogger('repomd')

__all__ = ('UpdateInfoXml', )

from rpath_xmllib import api1 as xmllib

from repomd.packagexml import PackageCompare
from repomd.xmlcommon import XmlFileParser, SlotNode
from repomd.errors import UnknownElementError, UnknownAttributeError

class _Updates(SlotNode):
    """
    Represents updates in an updateinfo.xml.
    """

    __slots__ = ()

    def addChild(self, child):
        """
        Set attributes on child nodes.
        """

        if child.getName() != 'update':
            raise UnknownElement(child)

        child.status = None
        child.emailfrom = None
        child.type = None
        child.version = None

        for attr, value in child.iterAttributes():
            if attr == 'status':
                child.status = value
            elif attr == 'from':
                child.emailfrom = value
            elif attr == 'type':
                child.type = value
            elif attr == 'version':
                child.version = value
            else:
                raise UnknownAttributeError(child, attr)

        SlotNode.addChild(self, child)

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
        'issued', 'references', 'description', 'pkglist', 'packages',
        'summary', 'packages', 'version')

    # All attributes are defined in __init__ by iterating over __slots__,
    # this confuses pylint.
    # W0201 - Attribute $foo defined outside __init__
    # pylint: disable-msg=W0201

    def addChild(self, child):
        """
        Parse the children of update.
        """

        #import epdb ; epdb.st()
        
        n = child.getName()
        if n == 'id':
            # Make this behave like SLES10 patchid
            self.id = child.finalize() + '-' + self.getAttribute('version')
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

    def __cmp__(self, other):
        vercmp = cmp(self.version, other.version)
        if vercmp != 0:
            return vercmp

        relcmp = cmp(self.release, other.release)
        if relcmp != 0:
            return relcmp

        # Is there even a summary in the schema?!?
        # There's a slot in mirrorball, but it's empty, and nothing in xml.
        #sumcmp = cmp(self.summary, other.summary)
        #if sumcmp != 0:
        #    return sumcmp

        desccmp = cmp(self.description, other.description)
        if desccmp != 0:
            return desccmp

        if self.issued != other.issued:
            maxtime = max(self.issued, other.issued)
            log.info('syncing timestamps (%s %s) ' % (self.issued,
                                                      other.issued) +
                     'for %s to %s' % (self.id, maxtime))
            self.issued = other.issued = maxtime
            # Don't return here--they're now equal.

        for pkg in other.pkglist:
            if pkg not in self.pkglist:
                self.pkglist.append(pkg)

        return 0

    def __hash__(self):
        return hash((self.id, self.release, self.summary, self.description))

class _References(SlotNode):
    """
    Represent a list of references in updateinfo.xml.
    """

    __slots__ = ()

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

        SlotNode.addChild(self, child)


class _Reference(SlotNode):
    """
    Prepesent a single reference.
    """

    __slots__ = ('href', 'id', 'title', 'type')


class _Collection(SlotNode):
    """
    Represents a pkglist collection in updateinfo.xml.
    """

    __slots__ = ()

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
        # SLES11 updateinfo.xml doesn't provide checksums or archive sizes.
        child.checksum = None
        child.archiveSize = None

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

        SlotNode.addChild(self, child)


class _UpdateInfoPackage(SlotNode, PackageCompare):
    """
    Represents a package entry in a pkglist of an update in updateinfo.xml.
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

    def getDegenerateNevra(self):
        """
        Return the name, epoch, version, release, and arch of the package.
        Return 0 for the epoch if otherwise undefined.
        """

        # SLES11 appears to leave epoch info out of metadata.
        if not self.epoch:
            return (self.name, u'0', self.version, self.release, self.arch)
        return (self.name, self.epoch, self.version, self.release, self.arch)
        
    def getNevra(self):
        """
        Return the name, epoch, version, release, and arch of the package.
        """

        return (self.name, self.epoch, self.version, self.release, self.arch)

    def __repr__(self):
        return os.path.basename(self.location)

    def __cmp__(self, other):
        pkgcmp = PackageCompare.__cmp__(self, other)
        if pkgcmp != 0:
            return pkgcmp

        # Compare arch before checksum to catch cases of multiple
        # arch-specific packages that happen to have same content
        # (e.g. SLES xorg-x11-fonts packages).
        archcmp = cmp(self.arch, other.arch)
        if archcmp != 0:
            return archcmp
        
        # Compare checksum only for equality, otherwise sorting will result in
        # checksum ordering.
        if (self.checksum and other.checksum and
            self.checksumType == other.checksumType and
            self.checksum == other.checksum):
            return 0
        
        # Compare on archiveSize for equality only. This is needed for rpms
        # that have identical contents, but may have been rebuilt. Idealy we
        # would use file checksums for this, but we don't have the payload
        # contents available at this time.
        if (self.archiveSize and other.archiveSize and
            self.archiveSize == other.archiveSize):
            return 0
        
        return cmp(self.location, other.location)
        
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
        self._databinder.registerType(_Reference, name='reference')
        self._databinder.registerType(_Collection, name='collection')
        self._databinder.registerType(_UpdateInfoPackage, name='package')

        self._databinder.registerType(xmllib.StringNode, name='id')
        self._databinder.registerType(xmllib.StringNode, name='title')
        self._databinder.registerType(xmllib.StringNode, name='release')
        self._databinder.registerType(xmllib.StringNode, name='description')
        self._databinder.registerType(xmllib.StringNode, name='filename')
