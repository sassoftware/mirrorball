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
Model representation of groups.
"""

from updatebot.lib.xobjects import XGroup
from updatebot.lib.xobjects import XGroupDoc
from updatebot.lib.xobjects import XGroupList
from updatebot.lib.xobjects import XPackageDoc
from updatebot.lib.xobjects import XPackageData
from updatebot.lib.xobjects import XPackageItem

class AbstractModel(object):
    """
    Base object for models.
    """

    docClass = None
    dataClass = None
    elementClass = None

    def __init__(self):
        self._data = {}
        self._nameMap = {}

    def _addItem(self, item):
        """
        Add an item to the appropriate structures.
        """

        self._data[item.key] = item
        if item.name not in self._nameMap:
            self._nameMap[item.name] = set()
        self._nameMap[item.name].add(item.key)

    def _removeItem(self, name, missingOk=False):
        """
        Remove an item from the appropriate structures.
        """

        if missingOk:
            keys = self._nameMap.pop(name, [])
        else:
            keys = self._nameMap.pop(name)

        for key in keys:
            self._data.pop(key)

    @classmethod
    def thaw(cls, xmlfn, args=None):
        """
        Thaw the model from xml.
        """

        model = cls.docClass.fromfile(xmlfn)
        obj = args and cls(*args) or cls()
        for item in model.data.items:
            obj._addItem(item)
        return obj

    def freeze(self, toFile):
        """
        Freeze the model to a given output file.
        """

        def _srtByKey(a, b):
            return cmp(a.key, b.key)

        model = self.dataClass()
        model.items = sorted(self._data.values(), cmp=_srtByKey)

        doc = self.docClass()
        doc.data = model
        doc.tofile(toFile)

    def iteritems(self):
        """
        Iterate over the model data.
        """

        return self._data.iteritems()

    def __iter__(self):
        """
        Iterate over the packages of this group.
        """

        return self._data.itervalues()

    def add(self, *args, **kwargs):
        """
        Add an data element.
        """

        obj = self.elementClass(*args, **kwargs)
        self._addItem(obj)

    def remove(self, name, missingOk=False):
        """
        Remove data element.
        """

        self._removeItem(name, missingOk=missingOk)

    def __contains__(self, name):
        """
        Check if element name is in the model.
        """

        return name in self._nameMap


class GroupModel(AbstractModel):
    """
    Model for representing group name and file name.
    """

    docClass = XGroupDoc
    dataClass = XGroupList
    elementClass = XGroup


class GroupContentsModel(AbstractModel):
    """
    Model for representing group data.
    """

    docClass = XPackageDoc
    dataClass = XPackageData
    elementClass = XPackageItem

    def __init__(self, groupName, byDefault=True, depCheck=True,
        checkPathConflicts=False):
        AbstractModel.__init__(self)
        self.groupName = groupName
        self.byDefault = byDefault
        self.depCheck = depCheck
        self.checkPathConflicts = checkPathConflicts

        # figure out file name based on group name
        name = ''.join([ x.capitalize() for x in self.groupName.split('-') ])
        self.fileName = name[0].lower() + name[1:] + '.xml'

    def removePackageFlavor(self, name, frzFlavor):
        """
        Remove a specific flavor from the group.
        """

        removed = []
        for pkgKey in self._nameMap[name]:
            pkg = self._data[pkgKey]
            if pkg.flavor == frzFlavor:
                self._data.pop(pkgKey)
                removed.append(pkgKey)

        for pkg in removed:
            self._nameMap[name].remove(pkg)

        if not self._nameMap[name]:
            self._nameMap.pop(name)
