#!/usr/bin/python
#
# Copyright (c) 2010 rPath, Inc.
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

mirrorballDir = os.path.abspath('../')
sys.path.insert(0, mirrorballDir)

if 'CONARY_PATH' in os.environ:
    sys.path.insert(0, os.environ['CONARY_PATH'])

import rmake
import conary
import updatebot

print >>sys.stderr, 'using conary from', os.path.dirname(conary.__file__)
print >>sys.stderr, 'using rmake from', os.path.dirname(rmake.__file__)
print >>sys.stderr, 'using updatebot from', os.path.dirname(updatebot.__file__)

from conary.lib import util
sys.excepthook = util.genExcepthook()

import logging

from updatebot import OrderedBot

log = logging.getLogger('tmplogger')

class Bot(OrderedBot):
    def generateInitialGroup(self):
        """
        Generate config for standard group contents based on repository history.
        """

        standard = (
 'aaa_base',
 'aaa_skel',
 'acl',
 'acpid',
 'ash',
 'at',
# 'atk',
# 'atk-devel',
# 'atk-doc',
 'attr',
# 'audiofile',
# 'audiofile-devel',
 'audit',
 'audit-devel',
 'audit-libs',
# 'autoconf',
# 'autofs',
 'bash',
# 'bc',
# 'bin86',
# 'bind',
# 'bind-chrootenv',
# 'bind-devel',
# 'bind-doc',
# 'bind-libs',
# 'bind-utils',
 'binutils',
# 'bison',
 'blt',
 'blocxx',
 'busybox',
 'bzip2',
# 'cairo',
# 'cairo-devel',
# 'cairo-doc',
# 'cdrecord',
# 'cdrecord-devel',
# 'cifs-mount',
# 'compat-libstdc++',
# 'compat-openssl097g',
 'coreutils',
 'cpio',
# 'cpp',
 'cracklib',
# 'cracklib-devel',
 'cron',
# 'curl',
# 'curl-devel',
# 'cvs',
# 'cvs-doc',
 'cyrus-sasl',
# 'cyrus-sasl-crammd5',
# 'cyrus-sasl-devel',
# 'cyrus-sasl-digestmd5',
# 'cyrus-sasl-gssapi',
# 'cyrus-sasl-otp',
# 'cyrus-sasl-plain',
# 'cyrus-sasl-sqlauxprop',
 'db',
 'db42',
# 'db-devel',
# 'db-utils',
 'dbus-1',
# 'dbus-1-devel',
 'dbus-1-glib',
# 'dbus-1-gtk',
# 'dbus-1-java',
# 'dbus-1-mono',
# 'dbus-1-python',
# 'dbus-1-qt3',
# 'dbus-1-qt3-devel',
# 'dbus-1-x11',
# 'dev86',
 'device-mapper',
# 'device-mapper-devel',
 'dhcpcd',
 'diffutils',
 'e2fsprogs',
# 'e2fsprogs-devel',
# 'eject',
# 'esound',
# 'esound-devel',
 'ethtool',
 'expat',
# 'expect',
 'file',
# 'file-devel',
 'filesystem',
 'fillup',
 'findutils',
# 'findutils-locate',
 'fontconfig',
# 'fontconfig-devel',
# 'freetype',
# 'freetype-tools',
 'freetype2',
# 'freetype2-devel',
 'gawk',
# 'gawk-doc',
# 'gcc',
# 'gcc-c++',
# 'gcc-fortran',
# 'gcc-info',
# 'gcc-java',
# 'gcc-locale',
# 'gcc-obj-c++',
# 'gcc-objc',
# 'gconf2',
# 'gconf2-devel',
# 'gconf2-doc',
# 'gdb',
 'gdbm',
# 'gdbm-devel',
 'gettext',
# 'gettext-devel',
 'glib2',
# 'glib2-devel',
# 'glib2-doc',
 'glibc',
# 'glibc-debuginfo',
# 'glibc-devel',
# 'glibc-html',
# 'glibc-i18ndata',
# 'glibc-info',
# 'glibc-locale',
# 'glibc-profile',
# 'glitz',
# 'glitz-devel',
# 'gmp',
# 'gmp-devel',
 'gnome-filesystem',
# 'gnome-vfs2',
# 'gnome-vfs2-devel',
# 'gnome-vfs2-doc',
# 'gnuplot',
# 'gnutls',
# 'gnutls-devel',
 'gpg',
# 'gpg2',
# 'gpm',
 'grep',
# 'groff',
 'grub',
# 'gtk2',
# 'gtk2-devel',
# 'gtk2-doc',
# 'gvim',
# 'gxdview',
 'gzip',
 'hal',
# 'hal-devel',
# 'hal-gnome',
# 'hdparm',
 'hwinfo',
# 'hwinfo-devel',
 'info',
 'insserv',
 'iproute2',
 'iptables',
# 'iptables-devel',
 'iputils',
# 'jpeg',
# 'kbd',
 'klogd',
 'krb5',
# 'krb5-apps-clients',
# 'krb5-apps-servers',
# 'krb5-client',
# 'krb5-devel',
# 'krb5-server',
# 'ksh',
# 'ksh-devel',
 'less',
 'libacl',
# 'libacl-devel',
 'libaio',
# 'libaio-devel',
# 'libapr-util1',
# 'libapr-util1-devel',
# 'libapr1',
# 'libapr1-devel',
# 'libart_lgpl',
# 'libart_lgpl-devel',
 'libattr',
# 'libattr-devel',
# 'libbonobo',
# 'libbonobo-devel',
# 'libbonobo-doc',
# 'libbonoboui',
# 'libbonoboui-devel',
# 'libbonoboui-doc',
 'libcap',
# 'libcap-devel',
 'libcom_err',
 'libelf',
 'libevent',
 'libgcc',
# 'libgcj',
# 'libgcj-devel',
 'libgcrypt',
# 'libgcrypt-devel',
# 'libgfortran',
# 'libgnome',
# 'libgnome-devel',
# 'libgnome-doc',
# 'libgnomecanvas',
# 'libgnomecanvas-devel',
# 'libgnomecanvas-doc',
 'libgpg-error',
# 'libgpg-error-devel',
# 'libgssapi',
# 'libidn',
# 'libidn-devel',
# 'libiniparser',
# 'libiniparser-devel',
# 'libjpeg',
# 'libjpeg-devel',
# 'libksba',
# 'libksba-devel',
# 'libmsrpc',
# 'libmsrpc-devel',
# 'libmudflap',
# 'libnlink',
 'libnscd',
# 'libnscd-devel',
# 'libobjc',
# 'libopencdk',
# 'libopencdk-devel',
# 'libpcap',
# 'libpng',
# 'libpng-devel',
# 'librpcsecgss',
# 'libsmbclient',
# 'libsmbclient-devel',
 'libstdc++',
# 'libstdc++-devel',
# 'libstdc++-doc',
 'libtool',
 'libusb',
 'libxcrypt',
# 'libxcrypt-devel',
 'libxml2',
# 'libxml2-devel',
# 'libxml2-python',
 'libxslt',
# 'libxslt-devel',
 'libzio',
 'limal',
 'limal-bootloader',
 'limal-perl',
 'logrotate',
# 'lsof',
 'lvm2',
# 'lzo',
# 'lzo-devel',
 'm4',
# 'mailx',
# 'make',
# 'man',
# 'mdadm',
# 'microcode_ctl',
 'mingetty',
 'mkinitrd',
# 'mkisofs',
 'mktemp',
# 'mm',
# 'mm-devel',
 'module-init-tools',
# 'mysql',
# 'mysql-Max',
# 'mysql-client',
# 'mysql-devel',
# 'mysql-shared',
# 'nc6',
 'ncurses',
# 'ncurses-devel',
# 'neon',
# 'net-snmp',
# 'net-snmp-devel',
 'net-tools',
 'netcfg',
# 'nfs-utils',
# 'nfsidmap',
# 'nmap',
# 'nmap-gtk',
 'nscd',
 'openct',
# 'openct-devel',
 'openldap2',
# 'openldap2-back-meta',
# 'openldap2-back-perl',
 'openldap2-client',
# 'openldap2-devel',
 'opensc',
# 'opensc-devel',
 'openslp',
# 'openslp-devel',
# 'openslp-server',
 'openssh',
# 'openssh-askpass',
 'openssl',
# 'openssl-devel',
# 'openssl-doc',
# 'orbit2',
# 'orbit2-devel',
 'pam',
# 'pam-devel',
 'pam-modules',
# 'pam_krb5',
# 'pam_smb',
# 'pango',
# 'pango-devel',
# 'pango-doc',
# 'parted',
# 'parted-devel',
# 'patch',
 'pciutils',
# 'pciutils-devel',
 'pciutils-ids',
 'pcre',
# 'pcre-devel',
 'pcsc-lite',
# 'pcsc-lite-devel',
 'perl',
# 'perl-Bit-Vector',
 'perl-Bootloader',
# 'perl-Carp-Clan',
# 'perl-Compress-Zlib',
# 'perl-DBD-SQLite',
# 'perl-DBD-mysql',
# 'perl-DBI',
# 'perl-Data-ShowTable',
# 'perl-Date-Calc',
# 'perl-Digest-SHA1',
# 'perl-Net-Daemon',
# 'perl-PlRPC',
# 'perl-SNMP',
# 'perl-TermReadKey',
# 'perl-URI',
# 'perl-XML-Parser',
# 'perl-XML-Writer',
 'perl-gettext',
 'permissions',
# 'pinentry',
# 'pkgconfig',
# 'pmtools',
 'popt',
# 'popt-devel',
# 'portmap',
# 'postgresql',
# 'postgresql-contrib',
# 'postgresql-devel',
# 'postgresql-docs',
# 'postgresql-libs',
# 'postgresql-server',
 'procmail',
 'procps',
 'psmisc',
 'pwdutils',
# 'pwdutils-plugin-audit',
 'python',
# 'python-cairo',
 'python-curses',
# 'python-demo',
 'python-devel',
 'python-gdbm',
# 'python-gnome',
# 'python-gtk',
# 'python-idle',
# 'python-numeric',
# 'python-orbit',
# 'python-pam',
 'python-tk',
 'python-xml',
 'readline',
# 'readline-devel',
 'reiserfs',
# 'resmgr',
 'rpm',
# 'rpm-devel',
 'rpm-python',
# 'rrdtool',
# 'rsync',
# 'samba',
# 'samba-client',
# 'samba-krb-printing',
# 'samba-python',
# 'samba-vscan',
# 'samba-winbind',
 'sed',
 'sendmail',
# 'sendmail-devel',
# 'sensors',
# 'slang',
# 'slang-devel',
 'sles-release',
# 'smartmontools',
# 'sqlite',
# 'sqlite-devel',
# 'strace',
# 'sudo',
 'sysconfig',
 'sysfsutils',
# 'syslinux',
 'syslog-ng',
 'syslogd',
# 'sysstat',
# 'sysstat-isag',
 'sysvinit',
 'suse-build-key',
 'tar',
 'tcl',
# 'tcl-devel',
 'tcpd',
# 'tcpd-devel',
# 'tcpdump',
 'tcsh',
# 'telnet',
# 'telnet-server',
 'termcap',
 'terminfo',
# 'texinfo',
 'timezone',
 'tk',
# 'tk-devel',
 'udev',
# 'unixODBC',
# 'unixODBC-devel',
# 'unzip',
# 'usbutils',
 'util-linux',
# 'uucp',
 'vim',
 'wget',
# 'wireless-tools',
# 'x11-tools',
 'xfsprogs',
# 'xfsprogs-devel',
# 'xinetd',
# 'xkeyboard-config',
# 'xntp',
# 'xntp-doc',
# 'xorg-x11',
# 'xorg-x11-Xnest',
# 'xorg-x11-Xvfb',
# 'xorg-x11-Xvnc',
# 'xorg-x11-devel',
# 'xorg-x11-doc',
# 'xorg-x11-fonts-100dpi',
# 'xorg-x11-fonts-75dpi',
# 'xorg-x11-fonts-cyrillic',
# 'xorg-x11-fonts-scalable',
# 'xorg-x11-fonts-syriac',
 'xorg-x11-libs',
# 'xorg-x11-man',
# 'xorg-x11-sdk',
# 'xorg-x11-server',
# 'xorg-x11-server-glx',
# 'yp-tools',
# 'ypbind',
# 'zip',
# 'zisofs-tools',
 'zlib',
# 'zlib-devel',
        )

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

        pkgs = set()
        for name, vMap in trvs.iteritems():
            if name.endswith(':source'):
                continue
            name = name.split(':')[0]
            for version, flavors in vMap.iteritems():
                data = (name, version, tuple(flavors))
                pkgs.add(data)

        group = self._groupmgr.getGroup()

        for name, version, flavors in pkgs:
            log.info('adding %s=%s' % (name, version))
            for flv in flavors:
                log.info('\t%s' % flv)
            group.addPackage(name, version, flavors)

        group.errataState = '0'
        group.version = '0'

        addReq = dict([ ('group-standard', [ (x, None) for x in standard ]), ])
        group.modifyContents(additions=addReq)

        group._groups['group-standard'].depCheck = False

        group.removePackage('samba-pdb')
        group.removePackage('kiwi-desc-xennetboot')

        group._copyVersions()
        group._sanityCheck()
        group._mgr._persistGroup(group)

        import epdb; epdb.st()

        group.commit()
        built = group.build()

        import epdb; epdb.st()

        return built

if __name__ == '__main__':
    from updatebot import config
    from updatebot import log as logSetup

    logSetup.addRootLogger()

    log = logging.getLogger('create group')

    cfg = config.UpdateBotConfig()
    cfg.read(mirrorballDir + '/config/%s/updatebotrc' % sys.argv[1])

    bot = Bot(cfg, None)
    bot._pkgSource.load()
    changes = bot.generateInitialGroup()

    import epdb; epdb.st()
