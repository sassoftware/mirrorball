#!/bin/bash
#
# Copyright (c) 2008 rPath, Inc.
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

cfg="--config-file $HOME/hg/mirrorball/config/centos/conaryrc -m promote --interactive"

date
time cvc promote $cfg \
    group-appliance:source=centos.rpath.com@rpath:centos-5-devel \
    platform-definition:source=centos.rpath.com@rpath:centos-5-devel \
    kernel=centos.rpath.com@rpath:centos-5-devel \
    anaconda-templates=centos.rpath.com@rpath:centos-5-devel \
    group-os=centos.rpath.com@rpath:centos-5-devel \
    /centos.rpath.com@rpath:centos-5-devel--/centos.rpath.com@rpath:centos-5 \
    /centos.rpath.com@rpath:centos-devel//centos-5-devel--/centos.rpath.com@rpath:centos-5 \
    /conary.rpath.com@rpl:devel//2--/centos.rpath.com@rpath:centos-5 \
    /conary.rpath.com@rpl:devel//2//centos.rpath.com@rpath:centos-5-devel--/centos.rpath.com@rpath:centos-5 \
    /conary.rpath.com@rpl:devel//centos.rpath.com@rpath:centos-5-devel--/centos.rpath.com@rpath:centos-5
