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


all: default-subdirs default-all

export TOPDIR = $(shell pwd)
export DISTDIR = $(TOPDIR)/mirrorball-$(VERSION)

SUBDIRS=updatebot repomd rpmimport pylint artifactory

extra_files = \
	Make.rules 		\
	Makefile		\
	Make.defs		\

dist_files = $(extra_files)

.PHONY: clean dist install subdirs

subdirs: default-subdirs

install: install-subdirs

clean: clean-subdirs default-clean

dist:
	if ! grep "^Changes in $(VERSION)" NEWS > /dev/null 2>&1; then \
		echo "no NEWS entry"; \
		exit 1; \
	fi
	$(MAKE) forcedist


archive: $(dist_files)
	rm -rf $(DISTDIR)
	mkdir $(DISTDIR)
	for d in $(SUBDIRS); do make -C $$d DIR=$$d dist || exit 1; done
	for f in $(dist_files); do \
		mkdir -p $(DISTDIR)/`dirname $$f`; \
		cp -a $$f $(DISTDIR)/$$f; \
	done; \
	tar cjf $(DISTDIR).tar.bz2 `basename $(DISTDIR)`

forcedist: archive

tag:
	hg tag -f rbuild-$(VERSION)

clean: clean-subdirs default-clean

include Make.rules
include Make.defs
 
# vim: set sts=8 sw=8 noexpandtab :
