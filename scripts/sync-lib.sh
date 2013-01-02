#!/bin/bash -ex
#
# Copyright (c) SAS Institute
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

SOURCE="$1"
DEST="$2"
shift 2

date
rsync -lErtO \
    --verbose \
    --bwlimit=700 \
    $SOURCE $DEST "$@" \
    | tee rsync.tmp

grep -A1000 'receiving incremental file list' rsync.tmp \
    | grep -B1000 'sent .* bytes' \
    | grep -v 'receiving incremental file list\|sent.*bytes\|^$\|^TIME$\|^timestamp.txt$' \
    >> rsync.log ||:

./hardlink.py -v 0 $DEST
