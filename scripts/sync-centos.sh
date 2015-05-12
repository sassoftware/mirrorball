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
