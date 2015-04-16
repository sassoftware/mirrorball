#!/bin/bash
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
