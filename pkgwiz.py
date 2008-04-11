#!/usr/bin/python
#
# Copyright (c) 2006,2008 rPath, Inc.
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

from conary import cvc, rpmhelper
import conary.lib.util
import os
from rpmimport import infomaker, recipemaker, rpmsource
import shutil
import sys

HELP_TEXT = """
pkgs <dir>|<pkg> [<dir>|<pkg> ...]
accounts <user>|<group> [<user>|<group> ...]

pkgs can be given individual RPMs or the root of a directory tree to walk.

When packages are imported, they will be checked against what's in the
repository.  If newer, then check new one in.

accounts will create user and/or group info- packages, using
information from the build system.
"""
sles10sp1prefix = '/srv/www/html/sle/'
sles10sp1pkgs = (
    'aaa_base',
    'acl',
    'apache2',
    'ash',
    'attr',
    'audit',
    'bash',
    'binutils',
    'busybox',
    'bzip2',
    'compat-libstdc++',
    'compat-openssl097g',
    'coreutils',
    'cpio',
    'cpp',
    'cracklib',
    'cron',
    'cyrus-sasl',
    'device-mapper',
    'db',
    'dbus-1',
    'dhcpcd',
    'diffutils',
    'e2fsprogs',
    'expat',
    'expect',
    'file',
    'filesystem',
    'fillup',
    'findutils',
    'findutils-locate',
    'fontconfig',
    'freetype',
    'freetype2',
    'gawk',
    'gcc',
    'gdbm',
    'glib2',
    'glibc',
    'gmp',
    'gpm',
    'grep',
    'grub',
    'gzip',
    'hal',
    'hwinfo',
    'insserv',
    'iproute2',
    'iptables',
    'iputils',
    #'java-1_4_2-sun',
    'jpeg',
    'kbd',
    'klogd',
    'krb5',
    'ksh',
    'less',
    'libaio',
    'libapr-util1',
    'libapr1',
    'libattr',
    'libcap',
    'libcom_err',
    'libelf',
    'libevent',
    'libgcc',
    'libgssapi',
    'libiniparser',
    'libjpeg',
    'libnscd',
    'libpcap',
    'libpng',
    'librpcsecgss',
    'libstdc++',
    'libtool',
    'libusb',
    'libxcrypt',
    'libxml2',
    'libxml2-python',
    'logrotate',
    'lvm2',
    'make',
    'mdadm',
    'mingetty',
    'mkinitrd',
    'mktemp',
    'mm',
    'module-init-tools',
    'ncurses',
    'net-tools',
    'netcfg',
    'nfs-utils',
    'nfsidmap',
    'openct',
    'openldap2',
    'openldap2-client',
    'opensc',
    'openslp',
    'openssh',
    'openssl',
    'pam',
    'pam-modules',
    'patch',
    'pciutils',
    'pcre',
    'perl',
    'perl-Bootloader',
    'perl-Compress-Zlib',
    'perl-DBD-SQLite',
    'perl-DBI',
    'perl-Digest-SHA1',
    'perl-Net-Daemon',
    'perl-PlRPC',
    'perl-TermReadKey',
    'perl-URI',
    'perl-gettext',
    'php5',
    'pkgconfig',
    'popt',
    'portmap',
    'procps',
    'psmisc',
    'pwdutils',
    'python',
    'python-xml',
    'resmgr',
    'samba',
    'sed',
    'slang',
    'sles-release',
    'strace',
    'sysconfig',
    'sysfsutils',
    'syslog-ng',
    'sysvinit',
    'tar',
    'tcl',
    'tcpd',
    'tcsh',
    'tcpdump',
    'termcap',
    'timezone',
    'udev',
    'unixODBC',
    'unzip',
    'util-linux',
    'vim',
    'wget',
    'wireless-tools',
    #'xorg-x11',
    'zlib',
    'zip',
    )

class PkgWiz:
    def __init__(self):
        self.cfg = None
        self.client = None
        self.repos = None
        self.rpmSource = rpmsource.RpmSource()
        self.recipeMaker = None

    def help(self):
        print HELP_TEXT

    def _setupRepo(self):
        if self.cfg:
            return
        from conary import conaryclient, conarycfg, versions, errors
        from conary import deps
        from conary.build import use

        self.cfg = conarycfg.ConaryConfiguration(readConfigFiles=True)
        self.cfg.read(os.path.dirname(__file__) + '/conaryrc')
        self.cfg.initializeFlavors()
        cvcCommand = cvc.CvcCommand()
        cvcCommand.setContext(self.cfg, dict())
        if not self.cfg.buildLabel and self.cfg.installLabelPath:
            self.cfg.buildLabel = self.cfg.installLabelPath[0]

        buildFlavor = deps.deps.parseFlavor('is:x86(i586,!i686)')
        self.cfg.buildFlavor = deps.deps.overrideFlavor(
            self.cfg.buildFlavor, buildFlavor)
        use.setBuildFlagsFromFlavor(None, self.cfg.buildFlavor, error=False)

        self.client = conaryclient.ConaryClient(self.cfg)
        self.repos = self.client.getRepos()
        self.recipeMaker = recipemaker.RecipeMaker(self.cfg, self.repos, self.rpmSource)

    def createPkgs(self, dirs):
        self._setupRepo()
        for dir in dirs:
            self.rpmSource.walk(dir)

        # {foo:source: {cfg.buildLabel: None}}
        srccomps = {}

        # {foo:source: foo-1.0-1.1.src.rpm}
        srcmap = {}
        for src in set(self.rpmSource.getSrpms(sles10sp1pkgs)):
            h = self.rpmSource.getHeader(self.rpmSource.srcPath[src])
            srccomp = h[rpmhelper.NAME] + ':source'
            srcmap[srccomp] = src
            srccomps[srccomp] = {self.cfg.buildLabel: None}
        d = self.repos.getTroveVersionsByLabel(srccomps)

        # Iterate over foo:source.
        for srccomp in set(srccomps.iterkeys()):
            srpm = srcmap[srccomp]
            pkgname = srccomp.split(':')[0]
            if srccomp not in d:
                self.recipeMaker.createManifest(pkgname, srpm, sles10sp1prefix)
            else:
                continue
                self.recipeMaker.updateManifest(pkgname, srpm, sles10sp1prefix)

    def createUsers(self, users):
        self._setupRepo()
        # Get all users and groups used in this run.
        users = set()
        groups = set()
        for src in self.rpmSource.getSrpms(slessp1pkgs):
            for rpm in self.rpmSource.rpmMap[src].values():
                header = self.rpmSource.getHeader(rpm)
                users = users.union(header[FILEUSERNAME])
                groups = groups.union(header[FILEGROUPNAME])

        infoMaker = infomaker.InfoMaker(cfg, repos, self.recipeMaker)
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
