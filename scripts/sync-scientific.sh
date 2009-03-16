#!/bin/bash
#
# Copyright (c) 2009 rPath, Inc.
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

SOURCE=rsync://rsync.scientificlinux.org/scientific/53
DEST=/l/scientific/

date
rsync -arv --progress --bwlimit=1024 --exclude iso $SOURCE $DEST

./hardlink.py $DEST