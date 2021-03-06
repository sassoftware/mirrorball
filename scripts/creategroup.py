#!/usr/bin/python
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


from _scriptsetup import getBot
import os
import sys

if __name__ == '__main__':
    import rmake
    print >>sys.stderr, 'using rmake from', os.path.dirname(rmake.__file__)

import logging

from updatebot import OrderedBot

log = logging.getLogger('create group')

class Bot(OrderedBot):
    def generateInitialGroup(self):
        """
        Generate config for standard group contents based on repository history.
        """

        self._pkgSource.load()

        log.info('getting latest troves')
        troves = self._updater._conaryhelper._getLatestTroves()

        # combine packages of the same name.
        trvs = {}
        for name, vMap in troves.iteritems():
            if name.endswith(':source'):
                continue
            name = name.split(':')[0]
            for version, flavors in vMap.iteritems():
                for flv in flavors:
                    trvs.setdefault(name, dict()).setdefault(version, set()).add(flv)

        # Filter out sources, groups, and components; gathering all of the
        # package versions.
        pkgs = set()
        for name, vMap in trvs.iteritems():
            if name.endswith(':source'):
                continue
            if name.startswith('group-'):
                continue
            name = name.split(':')[0]
            for version, flavors in vMap.iteritems():
                data = (name, version, tuple(flavors))
                pkgs.add(data)

        # Get the latest group model.
        group = self._groupmgr.getGroup()

        # Remove the existing packages group.
        group._groups.pop('group-packages', None)

        # Add content to the packages group, which will cause a new model to
        # be created.
        for name, version, flavors in pkgs:
            log.info('adding %s=%s' % (name, version))
            for flv in flavors:
                log.info('\t%s' % flv)
            group.addPackage(name, version, flavors)

        # Set the errata state and version to some defaults.
        group.errataState = 0
        group.version = '0'

        # Remove the existing standard group if there is one.
        group._groups.pop('group-standard', None)

        # Run through all of the adds and removes for the standard group.
        removals = set()
        nevras = dict([ (x.getNevra(), y)
            for x, y in self._pkgSource.srcPkgMap.iteritems() ])

        for updateId in range(0, group.errataState + 1):
            self._modifyGroups(updateId, group)

            for srcNevra in self._cfg.removeSource.get(updateId, ()):
                removals.update(set([ x.name for x in nevras[srcNevra] ]))

            removals |= set(self._cfg.updateRemovesPackages.get(updateId, ()))

        # Remove any packages that would have normally been removed at this
        # errataState.
        for name in removals:
            group.removePackage(name, missingOk=True)

        # Sanity check the group model and write out the current state so that
        # you can do a local test cook.
        group._copyVersions()
        group._sanityCheck()
        group._setGroupFlags()
        group._mgr._persistGroup(group)

        # You probably want to do a test cook if your groups here. It would be
        # nice if mirrorball could just do this for you, but it can't right now.
        # To run a test cook take a look at group._mgr._helper._checkoutCache to
        # find the directory where the checkout is and then run cvc cook from
        # that directory.
        import epdb; epdb.st()

        # Commit and build the group.
        group = group.commit()
        built = group.build()

        import epdb; epdb.st()

        return built

if __name__ == '__main__':
    bot = getBot(Bot, None)
    trvMap = bot.generateInitialGroup()

    import epdb; epdb.st()
