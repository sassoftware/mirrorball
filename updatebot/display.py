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

def displayTrovesForGroupRecipe(trvMap, indent=12):
    """
    Formats a troveMap to a list of packages to be included in a group recipe.
    @param trvMap dictionary of troves from a build
    @type trvMap: {srcTrvs: set((n, v, f), ..)}
    @return formatted string
    """

    names = set()
    for trvSet in trvMap.itervalues():
        for trv in trvSet:
            names.add(trv[0].split(':')[0])

    names = list(names)
    names.sort()

    ret = []
    for name in names:
        ret.append(' ' * indent + '\'%s\',' % name)

    return '\n'.join(ret)
