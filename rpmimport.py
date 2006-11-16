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


import os
import sys
import shutil

from conary import rpmhelper

# make local copies of tags for convenience
for tag in ('NAME', 'VERSION', 'RELEASE', 'SOURCERPM', 'FILEUSERNAME',
    'FILEGROUPNAME'):
    sys.modules[__name__].__dict__[tag] = getattr(rpmhelper, tag)
ARCH = 1022

class RpmSource:
    def __init__(self):
        # {srpm: {rpm: path}
        self.rpmMap = dict()

        # {name: srpm}
        self.revMap = dict()

        # {srpm: path}
        self.srcPath = dict()

        # {rpmfile: header}
        self.headers = dict()

    def getHeader(self, f):
        if f in self.headers:
            return self.headers[f]
        header = rpmhelper.readHeader(file(f))
        self.headers[f] = header
        return header

    def procBin(self, f, rpm):
        header = self.getHeader(f)
        self.headers[f] = header
        if SOURCERPM in header:
            srpm = header[SOURCERPM]
        if self.rpmMap.has_key(srpm):
            self.rpmMap[srpm][rpm] = f
        else:
            self.rpmMap[srpm] = {rpm: f}
        self.revMap[header[NAME]] = srpm

    def procSrc(self, f, rpm):
        self.srcPath[rpm] = f

    def walk(self, root):
        """
        Walk the tree rooted at root and collect information about rpms found.
        """

        for dirpath, dirnames, filenames in os.walk(root):
            for f in filenames:
                # ignore the 32-bit compatibility libs - we will
                # simply use the 32-bit components from the repository
                if '32bit' in f:
                    continue
                if f.endswith(".rpm"):
                    fullpath = os.path.join(dirpath, f)
                    if f.endswith(".src.rpm") or f.endswith('.nosrc.rpm'):
                        self.procSrc(fullpath, f)
                    else:
                        self.procBin(fullpath, f)

    def getSrpms(self):
        """
        Get all sources we think we need now.
        """

        bins = ['acl', 'alsa', 'attr', 'libattr', 'ash', 'bzip2',
                'insserv', 'coreutils', 'cpio', 'cracklib',
                'cyrus-sasl', 'dhcpcd', 'diffutils',
                'sles-release', 'e2fsprogs', 'expat', 'expect',
                'file', 'filesystem', 'findutils', 'findutils-locate',
                'fontconfig', 'freetype', 'gawk', 'gdbm', 'glib2',
                'glibc', 'glibc-locale', 'glibc-i18ndata',
                'glibc-devel', 'gmp', 'gpm', 'grep', 'grub', 'gzip',
                'aaa_base', 'sysconfig', 'procps', 'iproute2',
                'iptables', 'iputils', 'kbd', 'krb5', 'libaio',
                'libelf', 'libgcc', 'compat-libstdc++', 'libstdc++',
                'mdadm', 'mingetty', 'mkinitrd', 'mktemp',
                'module-init-tools', 'ncurses', 'net-tools',
                'openssl', 'pam', 'pam-modules', 'perl-Bootloader',
                'pwdutils', 'pcre', 'perl', 'perl-DBI', 'procps',
                'psmisc', 'python', 'sed', 'netcfg', 'pwdutils',
                'slang', 'sqlite', 'sysfsutils', 'klogd', 'syslog-ng',
                'sysvinit', 'tar', 'tcl', 'termcap', 'timezone',
                'udev', 'unixODBC', 'sysvinit', 'util-linux', 'vim',
                'cron', 'wget', 'wireless-tools', 'xorg-x11', 'zlib',
                'perl-Bootloader' ]
        # add rpm, popt, readline, bash, db, apache2
        srpms = list()
        for b in bins:
            srpms.append(self.revMap[b])
        return srpms

    def transformName(self, name):
        """
        In name, - => _, + => _plus.
        """

        return name.replace('-', '_').replace('+', '_plus')

    def quoteSequence(self, seq):
        """
        [a, b] => 'a', 'b'
        """

        return ', '.join("'%s'" % x for x in sorted(seq))

    def getArchs(self, src):
        """
        @return list that goes into the archs line in the recipe.
        """

        hdrs = [ self.getHeader(x) for x in self.rpmMap[src].itervalues() ]
        archs = set(h[ARCH] for h in hdrs)
        if 'i586' in archs and 'i686' in archs:
            # remove the base arch if we have an extra arch
            arch, extra = self.getExtraArchs(src)
            if arch == 'i686':
                archs.remove('i586')
        return archs

    def getNames(self, src):
        """
        @return list that goes into the rpms line in the recipe.
        """

        hdrs = [ self.getHeader(x) for x in self.rpmMap[src].itervalues() ]
        names = set(h[NAME] for h in hdrs)
        return names

    def getExtraArchs(self, src):
        """
        For the special case of RPMs that have components optimized for the
        i686 architecture while other components are at i586, then return
        ('i686', set(rpms that are i686 only)), otherwise return (None, None).
        """

        hdrs = [ self.getHeader(x) for x in self.rpmMap[src].itervalues() ]
        archMap = {}
        for h in hdrs:
            arch = h[ARCH]
            name = h[NAME]
            if arch in archMap:
                archMap[arch].add(name)
            else:
                archMap[arch] = set((name,))
        if 'i586' in archMap and 'i686' in archMap:
            if archMap['i586'] != archMap['i686']:
                return 'i686', archMap['i686']
        return None, None

    def createTemplate(self, src):
        """
        @return the content of the new recipe.
        """

        srchdr = self.getHeader(self.srcPath[src])
        l = []
        a = l.append
        a("loadSuperClass('rpmimport.recipe')")
        a('class %s(RPMImportRecipe):' %(self.transformName(srchdr[NAME])))
        a("    name = '%s'" %(srchdr[NAME]))
        a("    version = '%s_%s'" %(srchdr[VERSION], srchdr[RELEASE]))
        archs = self.getArchs(src)
        names = self.getNames(src)
        extras = self.getExtraArchs(src)[1]
        a('    rpms = [ %s ]' % self.quoteSequence(names))
        a('    archs = [ %s ]' % self.quoteSequence(archs))
        if extras:
            a("    extraArch = { 'i686': [ %s ] }" %self.quoteSequence(extras))
        a('')
        return '\n'.join(l)

class RecipeMaker:
    def __init__(self, cvc, cfg, repos, rpmSource):
        self.cvc = cvc
        self.cfg = cfg
        self.repos = repos
        self.rpmSource = rpmSource

    def create(self, pkgname, recipeContents, srpm = None):
        print 'creating initial template for', pkgname
        try:
            shutil.rmtree(pkgname)
        except OSError, e:
            pass
        self.cvc.sourceCommand(self.cfg, [ "newpkg", pkgname], {})
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
            self.cvc.sourceCommand(self.cfg, addfiles, {})
            self.cvc.sourceCommand(self.cfg, ['cook', recipe], {})
            self.cvc.sourceCommand(self.cfg,
                              [ 'commit' ],
                              { 'message':
                                'Automated initial commit of ' + recipe })
            self.cvc.sourceCommand(self.cfg, ['cook', pkgname], {})
        finally:
            os.chdir(cwd)

if __name__ == '__main__':
    from conary import conaryclient, conarycfg, versions, errors, cvc
    from conary import deps
    from conary.lib import util
    from conary.build import use

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

    # {foo:source: {cfg.buildLabel: None}}
    srccomps = {}

    # {foo:source: foo-1.0-1.1.src.rpm}
    srcmap = {}
    for src in rpmSource.getSrpms():
        h = rpmSource.getHeader(rpmSource.srcPath[src])
        srccomp = h[NAME] + ':source'
        srcmap[srccomp] = src
        srccomps[srccomp] = {cfg.buildLabel: None}
    d = repos.getTroveVersionsByLabel(srccomps)

    # Iterate over foo:source.
    for srccomp in srccomps.iterkeys():
        if srccomp not in d:
            src = srcmap[srccomp]
            pkgname = srccomp.split(':')[0]
            recipeMaker.create(pkgname, rpmSource.createTemplate(src), src)


    # Get all users and groups used in this run.
    users = set()
    groups = set()
    for src in rpmSource.getSrpms():
        for rpm in rpmSource.rpmMap[src].values():
            header = rpmSource.getHeader(rpm)
            users = users.union(header[FILEUSERNAME])
            groups = groups.union(header[FILEGROUPNAME])

    import infoimport
    infoMaker = infoimport.InfoMaker(cfg, repos, recipeMaker)
    infoMaker.makeInfo(users, groups)
