#!/bin/bash
#
# Copyright (c) 2008-2009 rPath, Inc.
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

if [ "$1" = "" ] ; then
    # see if $0 has the target in the name
    name=$(basename $0)
    tmp=${name#sync-fedora-}
    target=${tmp%.sh}
else
    target=$1
fi

if [ "$target" = "" ] ; then
    echo "Could not determine target"
    exit 1
fi

SOURCE=rsync://mirror.linux.ncsu.edu/fedora-linux-
DEST=/l/fedora/linux/

CMD="rsync -arv --progress --bwlimit=800 --exclude ppc --exclude ppc64 --exclude 9 --exclude 10 --exclude test --exclude testing"

date

# mirror data
$CMD --exclude repodata $SOURCE$target $DEST$target

# mirror repodata
$CMD $SOURCE$target $DEST$target

# cleanup mirror
$CMD --delete $SOURCE$target $DEST$target
