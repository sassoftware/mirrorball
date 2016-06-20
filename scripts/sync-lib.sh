#!/bin/bash -ex
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


SOURCE="$1"
DEST="$2"
shift 2 || exit 1

date
rsync -lErtO \
    --verbose \
    --bwlimit=1500 \
    $SOURCE $DEST "$@" \
    | tee rsync.tmp || exit 1

grep -A1000 'receiving incremental file list' rsync.tmp \
    | grep -B1000 'sent .* bytes' \
    | grep -v 'receiving incremental file list\|sent.*bytes\|^$\|^TIME$\|^timestamp.txt$' \
    >> rsync.log ||:

./hardlink.py -v 0 $DEST || exit 1
