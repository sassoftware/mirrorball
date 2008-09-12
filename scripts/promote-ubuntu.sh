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

cfg="--config-file $HOME/hg/mirrorball/config/ubuntu/conaryrc -m promote"

time cvc promote $cfg \
{{auto,build,c,}package,deb-import,factory-deb}:source=ubuntu.rb.rpath.com@rpath:ubuntu-devel \
    /ubuntu.rb.rpath.com@rpath:ubuntu-devel--/ubuntu.rpath.org@rpath:ubuntu-devel

time cvc promote $cfg \
    group-appliance:source=ubuntu.rb.rpath.com@rpath:ubuntu-hardy-devel \
    platform-definition:source=ubuntu.rb.rpath.com@rpath:ubuntu-hardy-devel \
    group-os=ubuntu.rb.rpath.com@rpath:ubuntu-hardy-devel \
    ubuntu.rb.rpath.com@rpath:ubuntu-hardy-devel--ubuntu.rpath.org@rpath:ubuntu-hardy-devel \

time cvc promote $cfg \
    group-appliance:source=ubuntu.rpath.org@rpath:ubuntu-hardy-devel \
    platform-defintion:source=ubuntu.rpath.org@rpath:ubuntu-hardy-devel \
    group-os=ubuntu.rpath.org@rpath:ubuntu-hardy-devel \
    /ubuntu.rpath.org@rpath:ubuntu-hardy-devel--/ubuntu.rpath.org@rpath:ubuntu-hardy \
    /conary.rpath.com@rpl:devel//conary.rpath.com@rpl:2--/ubuntu.rpath.org@rpath:ubuntu-hardy \
    /conary.rpath.com@rpl:devel//conary.rpath.com@rpl:2//ubuntu.rpath.org@rpath:ubuntu-hardy-devel--/ubuntu.rpath.org@rpath:ubuntu-hardy \
    /conary.rpath.com@rpl:devel//ubuntu.rpath.org@rpath:ubuntu-hardy-devel--/ubuntu.rpath.org@rpath:ubuntu-hardy
