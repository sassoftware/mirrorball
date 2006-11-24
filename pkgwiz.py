import conary.lib.util
import infoimport
import os
import rpmimport
import shutil
import sys

HELP_TEXT = """
pkgs <dir>|<pkg> [<dir>|<pkg> ...]
accounts <user>|<group> [<user>|<group> ...]

pkgs can be given individual RPMs or the root of a directory tree to walk.

When packages are imported, they will be checked against what's in the repository.  If newer, then check new one in.

accounts will create user and/or group info- packages, using information from the build system.
"""

class PkgWiz:
    def __init__(self):
        self.cfg = None
        self.client = None
        self.repos = None
        self.rpmSource = rpmimport.RpmSource()
        self.recipeMaker = None

    def help(self):
        print HELP_TEXT

    def repo(self):
        from conary import conaryclient, conarycfg, versions, errors
        from conary import deps
        from conary.build import use

        self.cfg = conarycfg.ConaryConfiguration(readConfigFiles=True)
        self.cfg.initializeFlavors()

        buildFlavor = deps.deps.parseFlavor('is:x86(i586,!i686)')
        self.cfg.buildFlavor = deps.deps.overrideFlavor(
            self.cfg.buildFlavor, buildFlavor)
        use.setBuildFlagsFromFlavor(None, self.cfg.buildFlavor, error=False)

        self.client = conaryclient.ConaryClient(self.cfg)
        self.repos = self.client.getRepos()
        self.recipeMaker = rpmimport.RecipeMaker(self.cfg, self.repos, self.rpmSource)

    def createPkgs(self, dirs):
        for dir in dirs:
            self.rpmSource.walk(dir)

        # {foo:source: {cfg.buildLabel: None}}
        srccomps = {}

        # {foo:source: foo-1.0-1.1.src.rpm}
        srcmap = {}
        for src in self.rpmSource.getSrpms():
            h = self.rpmSource.getHeader(self.rpmSource.srcPath[src])
            srccomp = h[NAME] + ':source'
            srcmap[srccomp] = src
            srccomps[srccomp] = {cfg.buildLabel: None}
        d = self.repos.getTroveVersionsByLabel(srccomps)

        # Iterate over foo:source.
        for srccomp in srccomps.iterkeys():
            src = srcmap[srccomp]
            pkgname = srccomp.split(':')[0]
            if srccomp not in d:
                self.recipeMaker.create(pkgname, self.rpmSource.createTemplate(src), src)
            else:
                # The package already exists in the repository, so query its
                # version.
                oldVersion = 1# FIXME
                # Get the version
                srchdr = self.rpmSource.getHeader(self.rpmSource.srcPath(src))
                newVersion = '%s_%s' % (srchdr[VERSION], srchdr[RELEASE])
                if newVersion == oldVersion:
                    continue

                # Check it out.
                from conary import cvc
                cvc.sourceCommand(self.cfg, ['checkout', pkgname])

                # Look for the version string and replace it with the new.
                import re
                pattern = re.compile("""(?P<lead>\\s+)version\\s*=\\s*['"]([^'"\\s]+_[^'"\\s]+)['"]\\s*$""")
                filename = os.path.join(pkgname, pkgname + ".recipe")
                recipeFile = open(filename)
                lines = recipeFile.readlines()
                recipeFile.close()
                spot = None
                for (index, line) in lines:
                    match = pattern.match(line)
                    if match:
                        spot = index
                        break
                if not spot:
                    raise Exception(
                        "The version string was not found in the %s recipe."
                        "  Is this correct?" %pkgname)
                lines = lines[:spot] + [match.group('lead')
                    + "version = '%s'\n" %newVersion] + lines[spot+1:]
                recipeFile = open(filename, 'w')
                recipeFile.write(''.join(lines))
                recipeFile.close()

                # Remove the original RPMs and add the new ones.
                import epdb
                epdb.st()
                cwd = os.getcwd()
                os.chdir(pkgname)
                from conary.state import ConaryStateFromFile
                conaryState = ConaryStateFromFile("CONARY", repos)
                state = conaryState.getSourceState()
                rpms = []
                for (theId, path, fileId, version) in state.iterFileList():
                    if path.endswith('rpm'):
                        rpms.append(path)
                for rpm in rpms:
                    cvc.sourceCommand(self.cfg, ['remove', rpm])
                addfiles = ['add']
                for path, fn in self.rpmSource.rpmMap[src].iteritems():
                    shutil.copy(fn, path)
                    addfiles.append(path)
                cvc.sourceCommand(self.cfg, addfiles, {})
                cvc.sourceCommand(self.cfg,
                    [ 'commit' ], {'message': 'Automated update of ' + pkgname})

    def test(self):
        import epdb
        epdb.st()
        from conary.state import ConaryStateFromFile
        conaryState = ConaryStateFromFile("/home/xiaowen/nuernberg/pwdutils/CONARY", self.repos)

    def createUsers(self, users):
        # Get all users and groups used in this run.
        users = set()
        groups = set()
        for src in self.rpmSource.getSrpms():
            for rpm in self.rpmSource.rpmMap[src].values():
                header = self.rpmSource.getHeader(rpm)
                users = users.union(header[FILEUSERNAME])
                groups = groups.union(header[FILEGROUPNAME])

        import infoimport
        infoMaker = infoimport.InfoMaker(cfg, repos, self.recipeMaker)
        infoMaker.makeInfo(users, groups)

    def main(self, argv):
        if '--debug' in argv:
            argv.remove('--debug')
            sys.excepthook = conary.lib.util.genExcepthook(debug=True)

        if len(argv) < 2:
            self.help()
            return
        category = argv[1]
        if 'pkgs' == category:
            dirs = argv[2:]
            if not dirs:
                dirs = ['.']
            self.test()
            self.createPkgs(dirs)
        elif 'accounts' == category:
            users = argv[2:]
            self.createUsers(users)
        else:
            self.help()
            return

if __name__ == '__main__':
    pkgWiz = PkgWiz()
    pkgWiz.main(sys.argv)
