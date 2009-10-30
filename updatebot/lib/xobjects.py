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
Module for serializable representations of repository metadata.
"""

from xobj import xobj

from aptmd.packages import _Package
from aptmd.sources import _SourcePackage

class XDocManager(xobj.Document):
    """
    Base class that implements simple freeze/thaw methods.
    """

    data = str
    freeze = xobj.Document.toxml

    @classmethod
    def thaw(cls, xml):
        """
        Deserialize an xml string into a DocManager instance.
        """

        return xobj.parse(xml, documentClass=cls)


class XMetadata(object):
    """
    Representation of repository data.
    """

    binaryPackages = [ _Package ]
    sourcePackage = _SourcePackage


class XMetadataDoc(XDocManager):
    """
    Document class for repository data.
    """

    data = XMetadata

    def __init__(self, *args, **kwargs):
        data = kwargs.pop('data', None)
        XDocManager.__init__(self, *args, **kwargs)
        if data is not None:
            self.data = XMetadata()
            self.data.binaryPackages = []
            for pkg in data:
                if pkg.arch == 'src':
                    self.data.sourcePackage = pkg
                else:
                    self.data.binaryPackages.append(pkg)


class XDictItem(object):
    """
    Object to represent key/value pairs.
    """

    key = str
    value = str

    def __init__(self, key=None, value=None):
        self.key = key
        self.value = value

    def __hash__(self):
        return hash(self.key)

    def __cmp__(self, other):
        if type(other) in (str, unicode):
            return cmp(self.key, other)
        else:
            return cmp(self.key, other.key)


class XDict(object):
    """
    String based xobj dict implementation.
    """

    items = [ XDictItem ]

    def __init__(self):
        self.items = []
        self._itemClass = self.__class__.__dict__['items'][0]

    def __setitem__(self, key, value):
        item = self._itemClass(key, value)
        if item in self.items:
            idx = self.items.index(item)
            self.items[idx] = item
        else:
            self.items.append(item)

    def __getitem__(self, key):
        if key in self.items:
            idx = self.items.index(key)
            return self.items[idx].value
        raise KeyError, key

    def __contains__(self, key):
        return key in self.items


class XItemList(XDocManager):
    """
    List of items.
    """

    def __init__(self):
        self.items = []
        self._itemClass = self.__class__.__dict__['items'][0]
        XDocManager.__init__(self)


class XPackageItem(object):
    """
    Object to represent package data required for group builds with the
    managed group factory.
    """

    name = str
    version = str
    flavor = str
    byDefault = int
    use = str
    source = str
    originalName = str

    def __init__(self, name, version='', flavor='', byDefault=1, use=1,
                 source='', originalName=None):
        self.name = name
        self.version = version
        self.flavor = flavor
        self.byDefault = byDefault
        self.use = use
        self.source = source
        self.originalName = originalName and originalName or name


class XPackageData(XItemList):
    """
    Mapping of package name to package group data.
    """

    items = [ XPackageItem ]


class XGroup(object):
    """
    Group file info.
    """

    name = str
    filename = str

    def __init__(self, name, filename):
        self.name = name
        self.filename = filename


class XGroupList(XItemList):
    """
    List of file names to load as groups.
    """

    items = [ XGroup ]
