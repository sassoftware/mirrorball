#
# Copyright (c) SAS Institute, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
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
