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
Module for parsing package sections of xml files from the repository metadata.
"""

__all__ = ('PackageXmlMixIn', 'PackageCompare', )

import os

from rpath_xmllib import api1 as xmllib

from updatebot.lib import util

from repomd.errors import UnknownElementError, UnknownAttributeError
from repomd.xmlcommon import SlotNode

class PackageCompare(object):
    def __str__(self):
        return '-'.join([self.name, self.epoch, self.version, self.release,
                         self.arch])

    def __hash__(self):
        # NOTE: We do not hash on epoch, because not all package objects will
        #       have epoch set. This will cause hash collisions that should be
        #       handled in __cmp__.
        return hash((self.name, self.version, self.release, self.arch))

    def __cmp__(self, other):
        return util.packageCompareByName(self, other)


class _Package(SlotNode, PackageCompare):
    """
    Python representation of package section of xml files from the repository
    metadata.
    """

    # R0902 - Too many instance attributes
    # pylint: disable-msg=R0902

    __slots__ = ('name', 'arch', 'epoch', 'version', 'release',
                 'checksum', 'checksumType', 'summary', 'description',
                 'fileTimestamp', 'buildTimestamp', 'packageSize',
                 'installedSize', 'archiveSize', 'location', 'format',
                 'license', 'vendor', 'group', 'buildhost',
                 'sourcerpm', 'headerStart', 'headerEnd',
                 'licenseToConfirm', 'files')

    # All attributes are defined in __init__ by iterating over __slots__,
    # this confuses pylint.
    # W0201 - Attribute $foo defined outside __init__
    # pylint: disable-msg=W0201


    def addChild(self, child):
        """
        Parse children of package element.
        """

        # R0912 - Too many branches
        # pylint: disable-msg=R0912

        # R0915 - Too many statements
        # pylint: disable-msg=R0915

        # E0203 - Access to member 'files' before its definition line 84
        # files is set to None by the superclasses __init__
        # pylint: disable-msg=E0203

        n = child.getName()
        if n == 'name':
            self.name = child.finalize()
        elif n == 'arch':
            self.arch = child.finalize()
        elif n == 'version':
            self.epoch = child.getAttribute('epoch')
            self.version = child.getAttribute('ver')
            self.release = child.getAttribute('rel')
        elif n == 'checksum':
            self.checksum = child.finalize()
            self.checksumType = child.getAttribute('type')
        elif n == 'summary':
            self.summary = child.finalize()
        elif n == 'description':
            self.description = child.finalize()
        elif n == 'packager':
            self.packager = child.finalize()
        elif n == 'url':
            self.url = child.finalize()
        elif n == 'time':
            self.fileTimestamp = child.getAttribute('file')
            self.buildTimestamp = child.getAttribute('build')
        elif n == 'size':
            self.packageSize = child.getAttribute('package')
            self.installedSize = child.getAttribute('installed')
            self.archiveSize = child.getAttribute('archive')
        elif n == 'location':
            self.location = child.getAttribute('href')
        elif n == 'file':
            if self.files is None:
                self.files = []
            self.files.append(child.finalize())
        elif child.getName() == 'format':
            self.format = []
            for node in child.iterChildren():
                nn = node.getName()
                if nn == 'rpm:license':
                    self.license = node.getText()
                elif nn == 'rpm:vendor':
                    self.vendor = node.getText()
                elif nn == 'rpm:group':
                    self.group = node.getText()
                elif nn == 'rpm:buildhost':
                    self.buildhost = node.getText()
                elif nn == 'rpm:sourcerpm':
                    self.sourcerpm = node.getText()
                elif nn == 'rpm:header-range':
                    self.headerStart = node.getAttribute('start')
                    self.headerEnd = node.getAttribute('end')
                elif nn in ('rpm:provides', 'rpm:requires',
                                        'rpm:obsoletes', 'rpm:recommends',
                                        'rpm:conflicts', 'suse:freshens',
                                        'rpm:enhances', 'rpm:supplements',
                                        'rpm:suggests', ):
                    self.format.append(node)
                elif nn == 'file':
                    pass
                else:
                    raise UnknownElementError(node)
        elif n == 'pkgfiles':
            pass
        elif n == 'suse:license-to-confirm':
            self.licenseToConfirm = child.finalize()
        else:
            raise UnknownElementError(child)

    def __repr__(self):
        return os.path.basename(self.location)

    def __cmp__(self, other):
        pkgcmp = PackageCompare.__cmp__(self, other)
        if pkgcmp != 0:
            return pkgcmp

        return cmp(self.location, other.location)

    def getNevra(self):
        """
        Return the name, epoch, version, release, and arch the package.
        """

        return (self.name, self.epoch, self.version, self.release, self.arch)

    def getConaryVersion(self):
        """
        Get the conary version of a source package.
        """

        assert self.arch == 'src'
        filename = os.path.basename(self.location)
        nameVerRelease = ".".join(filename.split(".")[:-2])
        ver = "_".join(nameVerRelease.split("-")[-2:])
        return ver


class _RpmEntry(xmllib.BaseNode):
    """
    Parse any element that contains rpm:entry or suse:entry elements.
    """

    def addChild(self, child):
        """
        Parse rpm:entry and suse:entry nodes.
        """

        if child.getName() in ('rpm:entry', 'suse:entry'):
            child.kind = None
            child.name = None
            child.epoch = None
            child.version = None
            child.release = None
            child.flags = None
            child.pre = None

            for attr, value in child.iterAttributes():
                if attr == 'kind':
                    child.kind = value
                elif attr == 'name':
                    child.name = value
                elif attr == 'epoch':
                    child.epoch = value
                elif attr == 'ver':
                    child.version = value
                elif attr == 'rel':
                    child.release = value
                elif attr == 'flags':
                    child.flags = value
                elif attr == 'pre':
                    child.pre = value
                else:
                    raise UnknownAttributeError(child, attr)
            xmllib.BaseNode.addChild(self, child)
        else:
            raise UnknownElementError(child)


class _RpmRequires(_RpmEntry):
    """
    Parse rpm:requires children.
    """


class _RpmRecommends(_RpmEntry):
    """
    Parse rpm:recommends children.
    """


class _RpmProvides(_RpmEntry):
    """
    Parse rpm:provides children.
    """


class _RpmObsoletes(_RpmEntry):
    """
    Parse rpm:obsoletes children.
    """


class _RpmConflicts(_RpmEntry):
    """
    Parse rpm:conflicts children.
    """


class _RpmEnhances(_RpmEntry):
    """
    Parse rpm:enhances children.
    """


class _RpmSupplements(_RpmEntry):
    """
    Parse rpm:supplements children.
    """


class _RpmSuggests(_RpmEntry):
    """
    Parse rpm:suggests children.
    """


class _SuseFreshens(_RpmEntry):
    """
    Parse suse:freshens children.
    """


class PackageXmlMixIn(object):
    """
    Handle registering all types for parsing package elements.
    """

    def _registerTypes(self):
        """
        Setup databinder to parse xml.
        """

        self._databinder.registerType(_Package, name='package')
        self._databinder.registerType(xmllib.StringNode, name='name')
        self._databinder.registerType(xmllib.StringNode, name='arch')
        self._databinder.registerType(xmllib.StringNode, name='checksum')
        self._databinder.registerType(xmllib.StringNode, name='summary')
        self._databinder.registerType(xmllib.StringNode, name='description')
        self._databinder.registerType(xmllib.StringNode, name='url')
        self._databinder.registerType(_RpmRequires, name='requires',
                                      namespace='rpm')
        self._databinder.registerType(_RpmRecommends, name='recommends',
                                      namespace='rpm')
        self._databinder.registerType(_RpmProvides, name='provides',
                                      namespace='rpm')
        self._databinder.registerType(_RpmObsoletes, name='obsoletes',
                                      namespace='rpm')
        self._databinder.registerType(_RpmConflicts, name='conflicts',
                                      namespace='rpm')
        self._databinder.registerType(_RpmEnhances, name='enhances',
                                      namespace='rpm')
        self._databinder.registerType(_RpmSupplements, name='supplements',
                                      namespace='rpm')
        self._databinder.registerType(_RpmSuggests, name='suggests',
                                      namespace='rpm')
        self._databinder.registerType(_SuseFreshens, name='freshens',
                                      namespace='suse')
        self._databinder.registerType(xmllib.StringNode,
                                      name='license-to-confirm',
                                      namespace='suse')
