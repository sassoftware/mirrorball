#!/bin/bash -xe

rsync -arv --progress --exclude iso --exclude 10.* --exclude ppc --exclude ppc64 rsync://rsync.opensuse.org/opensuse-full /mnt/rpath/linux/

./hardlink.py /mnt/rpath/linux/opensuse
