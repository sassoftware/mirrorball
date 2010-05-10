#
# Copyright (c) 2009-2010 rPath, Inc.
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
Conary interface for group content management.
"""

import os
import time
import logging

from updatebot.lib import util
from updatebot.conaryhelper import ConaryHelper

from updatebot.groupmgr.model import GroupModel
from updatebot.groupmgr.model import GroupContentsModel

log = logging.getLogger('updatebot.groupmgr')

GROUP_RECIPE = """\
#
# Copyright (c) %(year)s rPath, Inc.
# This file is distributed under the terms of the MIT License.
# A copy is available at http://www.rpath.com/permanent/mit-license.html
#
class %%(className)s(FactoryRecipeClass):
    \"\"\"
    Groups require that a recipe exists.
    \"\"\" 
""" % {'year': time.gmtime().tm_year, }


class GroupHelper(ConaryHelper):
    """
    Modified conary helper to deal with managing group sources.
    """

    def __init__(self, cfg):
        ConaryHelper.__init__(self, cfg)
        self._configDir = cfg.configPath
        self._newPkgFactory = 'managed-group'
        self._groupContents = cfg.groupContents

        # FIXME: autoLoadRecipes causes group versioning to go sideways
        # The group super class in the repository has a version defined, which
        # overrides the version from factory-version. This should probably be
        # considered a bug in factory-managed-group, but we don't need
        # autoLoadRecipes here anyway.
        self._ccfg.autoLoadRecipes = []

    def _newpkg(self, pkgName):
        """
        Wrap newpkg to add a group recipe since group recipes are required.
        """

        recipeDir = ConaryHelper._newpkg(self, pkgName)

        recipe = '%s.recipe' % pkgName
        recipeFile = os.path.join(recipeDir, recipe)
        if not os.path.exists(recipeFile):
            className = util.convertPackageNameToClassName(pkgName)
            fh = open(recipeFile, 'w')
            fh.write(GROUP_RECIPE % {'className': className})
            fh.close()
            self._addFile(recipeDir, recipe)

        return recipeDir

    def getModel(self, pkgName, version=None):
        """
        Get a thawed data representation of the group xml data from the
        repository.
        """

        log.info('loading model for %s' % pkgName)
        recipeDir = self._edit(pkgName, version=version)
        groupFileName = util.join(recipeDir, 'groups.xml')

        # load group model
        groups = {}
        if os.path.exists(groupFileName):
            model = GroupModel.thaw(groupFileName)
            for name, groupObj in model.iteritems():
                contentFileName = util.join(recipeDir, groupObj.filename)
                contentsModel = GroupContentsModel.thaw(contentFileName,
                                (name, groupObj.byDefault, groupObj.depCheck))
                contentsModel.fileName = groupObj.filename
                groups[groupObj.name] = contentsModel

        # copy in any group data
        for name, data in self._groupContents.iteritems():
            newGroups = [ x for x in groups.itervalues()
                            if x.groupName == name and
                               x.fileName == data['filename'] ]

            assert len(newGroups) in (0, 1)

            byDefault = data['byDefault'] == 'True' and True or False
            depCheck = data['depCheck'] == 'True' and True or False

            # load model
            contentsModel = GroupContentsModel.thaw(
                util.join(self._configDir, data['filename']),
                (name, byDefault, depCheck)
            )

            # override anything from the repo, unless retriveing a
            # specific version.
            if version is None:
                groups[name] = contentsModel

        return groups

    def setModel(self, pkgName, groups, version=None):
        """
        Freeze group model and save to the repository.
        """

        log.info('saving model for %s' % pkgName)
        recipeDir = self._edit(pkgName, version=version)
        groupFileName = util.join(recipeDir, 'groups.xml')

        groupModel = GroupModel()
        for name, model in groups.iteritems():
            groupfn = util.join(recipeDir, model.fileName)

            model.freeze(groupfn)
            groupModel.add(name=name,
                           filename=model.fileName,
                           byDefault=model.byDefault,
                           depCheck=model.depCheck)
            self._addFile(recipeDir, model.fileName)

        groupModel.freeze(groupFileName)
        self._addFile(recipeDir, 'groups.xml')

    def getErrataState(self, pkgname, version=None):
        """
        Get the contents of the errata state file from the specified package,
        if file does not exist, return None.
        """

        log.info('getting errata state information from %s' % pkgname)

        recipeDir = self._edit(pkgname, version=version)
        stateFileName = util.join(recipeDir, 'erratastate')

        if not os.path.exists(stateFileName):
            return None

        state = open(stateFileName).read().strip()
        if state.isdigit():
            state = int(state)
        return state

    def setErrataState(self, pkgname, state, version=None):
        """
        Set the current errata state for the given package.
        """

        log.info('storing errata state information in %s' % pkgname)

        recipeDir = self._edit(pkgname, version=version)
        stateFileName = util.join(recipeDir, 'erratastate')

        # write state info
        statefh = open(stateFileName, 'w')
        statefh.write(str(state))

        # source files must end in a trailing newline
        statefh.write('\n')

        statefh.close()

        # make sure state file is part of source trove
        self._addFile(recipeDir, 'erratastate')
