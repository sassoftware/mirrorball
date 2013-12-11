#!/bin/bash -ex
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

rm -f rsync.log

SOURCE=rsync://mirrors.us.kernel.org/CentOS-incdvd
DEST=/l/CentOS/

./sync-lib.sh "$SOURCE" "$DEST" \
    --exclude "2.*" \
    --exclude "3.*" \
    --exclude "*.drpm" \
    "$@" || exit 1

SOURCE=rsync://archive.kernel.org/centos-vault
DEST=/l/CentOS-vault/

./sync-lib.sh "$SOURCE" "$DEST" \
    --exclude "2.*" \
    --exclude "3.*" \
    --exclude "*.drpm" \
    "$@" || exit 1
