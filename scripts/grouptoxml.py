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


"""
Script to used to generate xml model for standard rhel groups.
"""

rhel4corePackages = (
    ('kernel', 'kernel.smp,!kernel.largesmp,!kernel.hugemem,!xen,!domU,!dom0'),
    'acl',
    'ash',
    'attr',
    'audit',
    'audit-libs',
    'authconfig',
    'basesystem',
    'bash',
    'beecrypt',
    'bzip2',
    'bzip2-libs',
    'checkpolicy',
    'chkconfig',
    'coreutils',
    'cpio',
    'cracklib',
    'cracklib-dicts',
    'crontabs',
    'cyrus-sasl',
    'cyrus-sasl-md5',
    'db4',
    'dbus',
    'dbus-glib',
    'device-mapper',
    'dhclient',
    'diffutils',
    'dmraid',
    'e2fsprogs',
    'ed',
    'elfutils-libelf',
    'ethtool',
    'expat',
    'file',
    'filesystem',
    'findutils',
    'fontconfig',
    'freetype',
    'gawk',
    'gdbm',
    'glib2',
    'glibc',
    'glibc-common',
    'gmp',
    'grep',
    'grub',
    'gzip',
    'hal',
    'hdparm',
    'hesiod',
    'hotplug',
    'hwdata',
    'indexhtml',
    'info',
    'initscripts',
    'iproute',
    'iptables',
    'iputils',
    'kbd',
    'krb5-libs',
    'kudzu',
    'less',
    'libacl',
    'libattr',
    'libcap',
    'libgcc',
    'libgcrypt',
    'libgpg-error',
    'libselinux',
    'libsepol',
    'libstdc++',
    'libtermcap',
    'libuser',
    'libxml2',
    'libxml2-python',
    'libxslt',
    'libxslt-python',
    'logrotate',
    'lvm2',
    'MAKEDEV',
    'mdadm',
    'mingetty',
    'mkinitrd',
    'mktemp',
    'module-init-tools',
    'ncurses',
    'net-tools',
    'newt',
    'nscd',
    'openldap',
    'openssl',
    'pam',
    'parted',
    'passwd',
    'pciutils',
    'pcre',
    'perl',
    'perl-Filter',
    'policycoreutils',
    'popt',
    'prelink',
    'procmail',
    'procps',
    'psmisc',
    'python',
    'pyxf86config',
    'readline',
    'redhat-logos',
    'redhat-release',
    'rhpl',
    'rootfiles',
    'rpm',
    'rpmdb-redhat',
    'rpm-libs',
    'sed',
    'selinux-doc',
    'selinux-policy-targeted',
    'sendmail',
    'setools',
    'setserial',
    'setup',
    'shadow-utils',
    'slang',
    'sysklogd',
    'system-config-mouse',
    'SysVinit',
    'tar',
    'tcp_wrappers',
    'termcap',
    'tmpwatch',
    'tzdata',
    'udev',
    'usbutils',
    'usermode',
    'util-linux',
    'vim-minimal',
    'vixie-cron',
    'wireless-tools',
    'xorg-x11-libs',
    'xorg-x11-Mesa-libGL',
    'zlib',
)


rhel5corePackages = (
    ('kernel', 'kernel.smp,!kernel.debug,!kernel.pae,!xen,!domU,!dom0'),
    'acl',
    'alchemist',
    'atk',
    'attr',
    'audit',
    'audit-libs',
    'audit-libs-python',
    'authconfig',
    'basesystem',
    'bash',
    'beecrypt',
    'bzip2',
    'bzip2-libs',
    'cairo',
    'checkpolicy',
    'chkconfig',
    'coreutils',
    'cpio',
    'cracklib',
    'cracklib-dicts',
    'crontabs',
    'cryptsetup-luks',
    'cups-libs',
    'cyrus-sasl',
    'cyrus-sasl-lib',
    'cyrus-sasl-md5',
    'db4',
    'dbus',
    'dbus-glib',
    'Deployment_Guide-en-US',
    'device-mapper',
    'device-mapper-multipath',
    'dhclient',
    'diffutils',
    'dmidecode',
    'dmraid',
    'e2fsprogs',
    'e2fsprogs-libs',
    'ed',
    'elfutils-libelf',
    'ethtool',
    'expat',
    'file',
    'filesystem',
    'findutils',
    'fontconfig',
    'freetype',
    'gawk',
    'gdbm',
    'glib2',
    'glibc',
    'glibc-common',
    'gmp',
    'gnutls',
    'grep',
    'grub',
    'gtk2',
    'gzip',
    'hal',
    'hdparm',
    'hesiod',
    'hicolor-icon-theme',
    'hwdata',
    'info',
    'initscripts',
    'iproute',
    'iptables',
    'iputils',
    'kbd',
    'kernel-headers',
    'keyutils-libs',
    'kpartx',
    'krb5-libs',
    'kudzu',
    'less',
    'libacl',
    'libattr',
    'libcap',
    'libgcc',
    'libgcrypt',
    'libgpg-error',
    'libhugetlbfs',
    'libhugetlbfs-lib',
    'libjpeg',
    'libpng',
    'libselinux',
    'libselinux-python',
    'libsemanage',
    'libsepol',
    'libstdc++',
    'libsysfs',
    'libtermcap',
    'libtiff',
    'libusb',
    'libuser',
    'libvolume_id',
    'libX11',
    'libXau',
    'libXcursor',
    'libXdmcp',
    'libXext',
    'libXfixes',
    'libXft',
    'libXi',
    'libXinerama',
    'libxml2',
    'libxml2-python',
    'libXrandr',
    'libXrender',
    'libxslt',
    'libxslt-python',
    'logrotate',
    'lvm2',
    'MAKEDEV',
    'mcstrans',
    'mdadm',
    'mingetty',
    'mkinitrd',
    'mktemp',
    'module-init-tools',
    'nash',
    'ncurses',
    'net-tools',
    'newt',
    'nscd',
    'openldap',
    'openssl',
    'pam',
    'pango',
    'parted',
    'passwd',
    'pciutils',
    'pcre',
    'pm-utils',
    'policycoreutils',
    'popt',
    'prelink',
    'procmail',
    'procps',
    'psmisc',
    'pycairo',
    'pygobject2',
    'pygtk2',
    'python',
    'python-numeric',
    'pyxf86config',
    'readline',
    'redhat-logos',
    'redhat-release',
    'redhat-release-notes',
    'rhpl',
    'rootfiles',
    'rpm',
    'rpm-libs',
    'sed',
    'selinux-policy',
    'selinux-policy-targeted',
    'sendmail',
    'setools',
    'setserial',
    'setup',
    'shadow-utils',
    'slang',
    'sqlite',
    'sysfsutils',
    'sysklogd',
    'SysVinit',
    'tar',
    'tcl',
    'tcp_wrappers',
    'termcap',
    'tmpwatch',
    'tzdata',
    'udev',
    'usbutils',
    'usermode',
    'util-linux',
    'vim-minimal',
    'vixie-cron',
    'wireless-tools',
    'xorg-x11-filesystem',
    'zlib',
)

import os
import sys
import time
import logging

sys.path.insert(0, os.environ['HOME'] + '/hg/conary')
sys.path.insert(0, os.environ['HOME'] + '/hg/xobj/py')
sys.path.insert(0, os.environ['HOME'] + '/hg/rbuilder-trunk/rpath-xmllib')

from conary.lib import util
sys.excepthook = util.genExcepthook()

from conary.deps import deps

mbdir = os.path.abspath('../')
sys.path.insert(0, mbdir)

from updatebot import log
from updatebot import groupmgr

slog = log.addRootLogger()

def toxml(pkgList, toFile):
    groupName = 'group-rhel-standard'
    byDefault = True
    depCheck = True

    contents = groupmgr.GroupContentsModel(groupName,
                                           byDefault=byDefault,
                                           depCheck=depCheck)

    for pkg in pkgList:
        slog.info('adding %s' % (pkg, ))
        if type(pkg) == tuple:
            pkg, flavor = pkg
            contents.add(pkg, flavor=deps.parseFlavor(flavor))
        else:
            contents.add(pkg)

    contents.freeze(toFile)


if __name__ == '__main__':
    platforms = {
        'rhel4': rhel4corePackages,
        'rhel5': rhel5corePackages,
    }

    platform = sys.argv[1]
    assert platform in platforms

    toFile = sys.argv[2]

    pkgs = platforms[platform]
    toxml(pkgs, toFile)
