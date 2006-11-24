class RecipeMaker:
    def __init__(self, cfg, repos, rpmSource):
        self.cfg = cfg
        self.repos = repos
        self.rpmSource = rpmSource

    def create(self, pkgname, recipeContents, srpm = None):
        from conary import cvc

        print 'creating initial template for', pkgname
        try:
            shutil.rmtree(pkgname)
        except OSError, e:
            pass
        cvc.sourceCommand(self.cfg, [ "newpkg", pkgname], {})
        cwd = os.getcwd()
        os.chdir(pkgname)
        try:
            recipe = pkgname + '.recipe'
            f = open(recipe, 'w')
            f.write(recipeContents)
            f.close()
            addfiles = [ 'add', recipe ]

            # copy all the binaries to the cwd
            if srpm:
                for path, fn in self.rpmSource.rpmMap[src].iteritems():
                    shutil.copy(fn, path)
                    addfiles.append(path)
            cvc.sourceCommand(self.cfg, addfiles, {})
            cvc.sourceCommand(self.cfg, ['cook', recipe], {'no-deps': None})
            cvc.sourceCommand(self.cfg,
                              [ 'commit' ],
                              { 'message':
                                'Automated initial commit of ' + recipe })
            cvc.sourceCommand(self.cfg, ['cook', pkgname], {'no-deps': None})
        finally:
            os.chdir(cwd)
