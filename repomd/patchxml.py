#
# Copryright (c) 2008 rPath, Inc.
#

'''
Module for parsing patch-*.xml files from the repository metadata.
'''

__all__ = ('PatchXml', )

from rpath_common.xmllib import api1 as xmllib

from repomd.xmlcommon import XmlFileParser, SlotNode
from repomd.packagexml import PackageXmlMixIn
from repomd.errors import UnknownElementError

class _Patch(SlotNode):
    '''
    Python representation of patch-*.xml from the repository metadata.
    '''
    __slots__ = ('name', 'summary', 'description', 'version',
                 'release', 'requires', 'recommends', 'rebootNeeded',
                 'licenseToConfirm', 'packageManager', 'category',
                 'packages')

    def addChild(self, child):
        '''
        Parse children of patch element.
        '''

        # FIXME: There should be a better way to setup a parser.
        # R0912 - Too many branches
        # pylint: disable-msg=R0912

        if child.getName() == 'yum:name':
            self.name = child.finalize()
        elif child.getName() == 'summary':
            if child.getAttribute('lang') == 'en':
                self.summary = child.finalize()
        elif child.getName() == 'description':
            if child.getAttribute('lang') == 'en':
                self.description = child.finalize()
        elif child.getName() == 'yum:version':
            self.version = child.getAttribute('ver')
            self.release = child.getAttribute('rel')
        elif child.getName() == 'rpm:requires':
            self.requires = child.getChildren('entry', namespace='rpm')
        elif child.getName() == 'rpm:recommends':
            self.recommends = child.getChildren('entry', namespace='rpm')
        elif child.getName() == 'reboot-needed':
            self.rebootNeeded = True
        elif child.getName() == 'license-to-confirm':
            self.licenseToConfirm = child.finalize()
        elif child.getName() == 'package-manager':
            self.packageManager = True
        elif child.getName() == 'category':
            self.category = child.finalize()
        elif child.getName() == 'atoms':
            self.packages = child.getChildren('package')
        else:
            raise UnknownElementError(child)

    def __cmp__(self, other):
        if self.version > other.version:
            return 1
        elif self.version < other.version:
            return -1
        elif self.release > other.release:
            return 1
        elif self.release < other.release:
            return -1
        else:
            return 0


class _Atoms(xmllib.BaseNode):
    '''
    Parser for the atoms element of a path-*.xml file.
    '''

    def addChild(self, child):
        '''
        Parse children of atoms element.
        '''

        if child.getName() == 'package':
            child.type = child.getAttribute('type')
            xmllib.BaseNode.addChild(self, child)
        elif child.getName() == 'message':
            pass
        elif child.getName() == 'script':
            pass
        else:
            raise UnknownElementError(child)


class PatchXml(XmlFileParser, PackageXmlMixIn):
    '''
    Handle registering all types for parsing patch-*.xml files.
    '''

    # R0903 - Too few public methods
    # pylint: disable-msg=R0903

    def _registerTypes(self):
        '''
        Setup databinder to parse xml.
        '''

        PackageXmlMixIn._registerTypes(self)
        self._databinder.registerType(_Patch, name='patch')
        self._databinder.registerType(xmllib.StringNode, name='name',
                                      namespace='yum')
        self._databinder.registerType(xmllib.StringNode, name='category')
        self._databinder.registerType(_Atoms, name='atoms')
        self._databinder.registerType(xmllib.StringNode,
                                      name='license-to-confirm')
