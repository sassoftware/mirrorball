#!/bin/bash -xe

date
rsync -arv --exclude iso --exclude 10.* --exclude ppc --exclude ppc64 rsync://rsync.opensuse.org/opensuse-full/opensuse/ /mnt/rpath/linux/opensuse

./hardlink.py /mnt/rpath/linux/opensuse
