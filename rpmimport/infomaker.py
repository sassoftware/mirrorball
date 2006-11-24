#!/usr/bin/python
#
# Copyright (c) 2006 rPath, Inc.
#
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


import grp
import pwd
import sys

class InfoMaker:
    def __init__(self, cfg, repos, recipeMaker):
        self.cfg = cfg
        self.repos = repos
        self.recipeMaker = recipeMaker

    def closeUser(self, user, users, groups, ustaging, gstaging, ugMap):
        """
        If a user has supplemental groups, then create those.
        """
        try:
            uprop = pwd.getpwnam(user)
        except KeyError, e:
            print "The user %s does not exist on the build system." \
                "  Please create it before running this." % (user)
            return

        (uid, gid, comment, homedir, shell) = uprop[2:]
        gprop = grp.getgrgid(gid)
        group = gprop[0]
        supgroups = ugMap.get(user, set()).difference(set([group]))
        for g in supgroups:
            if g not in groups:
                gstaging.add(g)
        users.add(user)

    def closeGroup(self, group, users, groups, ustaging, gstaging, ugMap):
        """
        If there is a user with this as its primary group, then create the user
        instead.
        """

        try:
            gprop = grp.getgrnam(group)
        except KeyError, e:
            print "The group %s does not exist on the build system." \
                "  Please create it first before running this." % (group)
            return

        gid = gprop[2]
        primaries = gprop[3] + [group]
        for u in primaries:
            try:
                uprop = pwd.getpwnam(u)
                if uprop[3] == gid:
                    ustaging.add(uprop[0])
                    return
            except KeyError, e:
                # No such user, oh well, ignore.
                pass
        groups.add(group)

    def makeInfo(self, users, groups):
        # Map username to groups it belongs to.
        ugMap = dict()
        for (g, a, b, us) in grp.getgrall():
            for u in us:
                if u in ugMap:
                    ugMap[u].add(g)
                else:
                    ugMap[u] = set([g])

        # Groups and users depend on each other, so do their closure.
        ustaging = users
        gstaging = groups
        users = set()
        groups = set()
        while ustaging or gstaging:
            for user in ustaging:
                self.closeUser(user, users, groups, ustaging, gstaging, ugMap)
            ustaging = set()
            for group in gstaging:
                self.closeGroup(group, users, groups, ustaging, gstaging, ugMap)
            gstaging = set()

        # Remove the root user and group.
        users = users.difference(['root'])
        groups = groups.difference(['root'])

        # If there are groups named the same as the user, then the user must
        # have this group as its primary group.
        groups = groups.difference(users)

        # All the packages we might create.
        srccomps = {}
        for account in users.union(groups):
            srccomps['info-%s:source' % (account)] = {self.cfg.buildLabel: None}

        # Get current repository contents.
        repoContents = self.repos.getTroveVersionsByLabel(srccomps)

        # Create users.
        for user in users:
            # If it already exists, then move on.
            if 'info-%s:source' %user in repoContents:
                continue

            uprop = pwd.getpwnam(user)
            (uid, gid, comment, homedir, shell) = uprop[2:]
            gprop = grp.getgrgid(gid)
            group = gprop[0]
            supgroups = ugMap.get(user, set()).difference(set([group]))

            self.recipeMaker.create('info-%s' % (user),
                "class info_%(user)s(UserInfoRecipe):\n"
                "    name = 'info-%(user)s'\n"
                "    version = '1'\n"
                "\n"
                "    def setup(r):\n"
                "        r.User('%(user)s', %(uid)s, group='%(group)s', groupid=%(gid)s,\n"
                "            homedir='%(homedir)s', comment='%(comment)s', shell='%(shell)s',\n"
                "            supplemental=[%(supgroups)s])\n"
                % dict(user=user, uid=uid, group=group, gid=gid,
                    homedir=homedir, comment=comment, shell=shell,
                    supgroups=', '.join("'%s'" % g for g in supgroups)))

        # Create groups.
        for group in groups:
            # If it already exists, then move on.
            if 'info-%s:source' %group in repoContents:
                continue

            gprop = grp.getgrnam(group)
            gid = gprop[2]

            # Create the group recipe.
            self.recipeMaker.create('info-%s' % (group),
                "class info_%(group)s(GroupInfoRecipe):\n"
                "    name = 'info-%(group)s'\n"
                "    version = '1'\n"
                "\n"
                "    def setup(r):\n"
                "        r.Group('%(group)s', %(gid)s)\n"
                % dict(group=group, gid=gid))

if __name__ == '__main__':
    from conary import conaryclient, conarycfg, versions, errors, cvc
    from conary import deps
    from conary.lib import util
    from conary.build import use
    from rpmimport import RecipeMaker, RpmSource

    sys.excepthook = util.genExcepthook(debug=True)

    cfg = conarycfg.ConaryConfiguration(readConfigFiles=True)
    cfg.initializeFlavors()

    buildFlavor = deps.deps.parseFlavor('is:x86(i586,!i686)')
    cfg.buildFlavor = deps.deps.overrideFlavor(cfg.buildFlavor,
                                               buildFlavor)
    use.setBuildFlagsFromFlavor(None, cfg.buildFlavor, error=False)

    client = conaryclient.ConaryClient(cfg)
    repos = client.getRepos()
    roots = sys.argv[1:]
    rpmSource = RpmSource()
    for root in roots:
        rpmSource.walk(root)
    recipeMaker = RecipeMaker(cvc, cfg, repos, rpmSource)

    infoMaker = InfoMaker(cfg, repos, recipeMaker)
    infoMaker.makeInfo(set(['video']), set())
