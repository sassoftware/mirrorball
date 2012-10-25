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

def displayTroveMap(trvMap, indent=4):
    """
    Format a mapping of source to binaries.
    @param trvMap dictionary of troves from a build
    @type trvMap: {srcTrvs: set((n, v, f), ..)}
    @return formatted string
    """

    tab = ' ' * indent

    ret = []
    for src, bins in sorted(trvMap.iteritems()):
        ret.append('%s=%s' % (src[0], src[1]))
        for bin in sorted(bins):
            ret.append('%s%s=%s[%s]' % (tab, bin[0], bin[1], bin[2]))

    return '\n'.join(ret)
