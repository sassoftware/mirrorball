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


SOURCE=rsync://rsync.scientificlinux.org/scientific/
DEST=/l/scientific/

rm -f rsync.log
./sync-lib.sh "$SOURCE" "$DEST" \
    --exclude "5*" \
    --exclude "6rolling/" \
    --exclude "6x/" \
    --exclude "*.drpm" \
    --exclude "iso" \
    --exclude "livecd" \
    --exclude "mirrorlist" \
    --exclude "obsolete" \
    --exclude "repoview" \
    --exclude ".repoview.new" \
    --exclude "RHAPS*" \
    --exclude "sites" \
    --exclude "virtual?images" \
    "$@" || exit 1
