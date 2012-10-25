#!/bin/bash
#
# Copyright (c) rPath, Inc.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
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
