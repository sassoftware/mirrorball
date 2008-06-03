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

"""
Module for parsing package sections of xml files from the repository metadata.
"""

__all__ = ('PackageXmlMixIn', )

from rpath_common.xmllib import api1 as xmllib

from repomd.errors import UnknownElementError, UnknownAttributeError
from repomd.xmlcommon import SlotNode

class _Package(SlotNode):
    """
    Python representation of package section of xml files from the repository
    metadata.
    """
    __slots__ = ('name', 'arch', 'epoch', 'version', 'release',
                 'checksum', 'checksumType', 'summary', 'description',
                 'fileTimestamp', 'buildTimestamp', 'packageSize',
                 'installedSize', 'archiveSize', 'location', 'format',
                 'license', 'vendor', 'group', 'buildhost',
                 'sourcerpm', 'headerStart', 'headerEnd',
                 'licenseToConfirm')

    def addChild(self, child):
        """
        Parse children of package element.
        """

        # FIXME: There should be a better way to setup a parser.
        # R0912 - Too many branches
        # pylint: disable-msg=R0912

        # R0915 - Too many statements
        # pylint: disable-msg=R0915

        if child.getName() == 'name':
            self.name = child.finalize()
        elif child.getName() == 'arch':
            self.arch = child.finalize()
        elif child.getName() == 'version':
            self.epoch = child.getAttribute('epoch')
            self.version = child.getAttribute('ver')
            self.release = child.getAttribute('rel')
        elif child.getName() == 'checksum':
            self.checksum = child.finalize()
            self.checksumType = child.getAttribute('type')
        elif child.getName() == 'summary':
            self.summary = child.finalize()
        elif child.getName() == 'description':
            self.description = child.finalize()
        elif child.getName() == 'packager':
            self.packager = child.finalize()
        elif child.getName() == 'url':
            self.url = child.finalize()
        elif child.getName() == 'time':
            self.fileTimestamp = child.getAttribute('file')
            self.buildTimestamp = child.getAttribute('build')
        elif child.getName() == 'size':
            self.packageSize = child.getAttribute('package')
            self.installedSize = child.getAttribute('installed')
            self.archiveSize = child.getAttribute('archive')
        elif child.getName() == 'location':
            self.location = child.getAttribute('href')
        elif child.getName() == 'format':
            self.format = []
            for node in child.iterChildren():
                if node.getName() == 'rpm:license':
                    self.license = node.getText()
                elif node.getName() == 'rpm:vendor':
                    self.vendor = node.getText()
                elif node.getName() == 'rpm:group':
                    self.group = node.getText()
                elif node.getName() == 'rpm:buildhost':
                    self.buildhost = node.getText()
                elif node.getName() == 'rpm:sourcerpm':
                    self.sourcerpm = node.getText()
                elif node.getName() == 'rpm:header-range':
                    self.headerStart = node.getAttribute('start')
                    self.headerEnd = node.getAttribute('end')
                elif node.getName() in ('rpm:provides', 'rpm:requires',
                                        'rpm:obsoletes', 'rpm:recommends',
                                        'rpm:conflicts', 'suse:freshens',
                                        'rpm:enhances', 'rpm:supplements',
                                        'rpm:suggests', ):
                    self.format.append(node)
                elif node.getName() == 'file':
                    pass
                else:
                    raise UnknownElementError(node)
        elif child.getName() == 'pkgfiles':
            pass
        elif child.getName() == 'suse:license-to-confirm':
            self.licenseToConfirm = child.finalize()
        else:
            raise UnknownElementError(child)

    def __str__(self):
        return '%(name)s-%(version)s-%(release)s' % self.__dict__


class _RpmRequires(xmllib.BaseNode):
    """
    Parse any element that contains rpm:entry or suse:entry elements.
    """

    def addChild(self, child):
        """
        Parse rpm:entry and suse:entry nodes.
        """

        if child.getName() in ('rpm:entry', 'suse:entry'):
            for attr, value in child.iterAttributes():
                child.kind = None
                child.name = None
                child.epoch = None
                child.version = None
                child.release = None
                child.flags = None
                child.pre = None

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


class _RpmRecommends(_RpmRequires):
    """
    Parse rpm:recommends children.
    """


class _RpmProvides(_RpmRequires):
    """
    Parse rpm:provides children.
    """


class _RpmObsoletes(_RpmRequires):
    """
    Parse rpm:obsoletes children.
    """


class _RpmConflicts(_RpmRequires):
    """
    Parse rpm:conflicts children.
    """


class _RpmEnhances(_RpmRequires):
    """
    Parse rpm:enhances children.
    """


class _RpmSupplements(_RpmRequires):
    """
    Parse rpm:supplements children.
    """


class _RpmSuggests(_RpmRequires):
    """
    Parse rpm:suggests children.
    """


class _SuseFreshens(_RpmRequires):
    """
    Parse suse:freshens children.
    """


class PackageXmlMixIn(object):
    """
    Handle registering all types for parsing package elements.
    """

    # R0903 - Too few public methods
    # pylint: disable-msg=R0903

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
        # FIXME: really shouldn't need to comment these out
        # self._databinder.registerType(xmllib.StringNode, name='license',
        #                               namespace='rpm')
        # self._databinder.registerType(xmllib.StringNode, name='vendor',
        #                               namespace='rpm')
        # self._databinder.registerType(xmllib.StringNode, name='group',
        #                               namespace='rpm')
        # self._databinder.registerType(xmllib.StringNode, name='buildhost',
        #                               namespace='rpm')
        # self._databinder.registerType(xmllib.StringNode, name='sourcerpm',
        #                               namespace='rpm')
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
