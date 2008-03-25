#
# Copyright (c) 2006,2008 rPath, Inc.
#
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


import os
import sys
import shutil

from conary import rpmhelper

# make local copies of tags for convenience
for tag in ('NAME', 'VERSION', 'RELEASE', 'SOURCERPM', 'FILEUSERNAME',
            'FILEGROUPNAME'):
    sys.modules[__name__].__dict__[tag] = getattr(rpmhelper, tag)
ARCH = 1022

class RpmSource:
    def __init__(self):
        # {srpm: {rpm: path}
        self.rpmMap = dict()

        # {name: srpm}
        self.revMap = dict()

        # {srpm: path}
        self.srcPath = dict()

        # {rpmfile: header}
        self.headers = dict()

    def getHeader(self, f):
        if f in self.headers:
            return self.headers[f]
        header = rpmhelper.readHeader(file(f))
        self.headers[f] = header
        return header

    def procBin(self, f, rpm):
        header = self.getHeader(f)
        self.headers[f] = header
        if SOURCERPM in header:
            srpm = header[SOURCERPM]
        if self.rpmMap.has_key(srpm):
            self.rpmMap[srpm][rpm] = f
        else:
            self.rpmMap[srpm] = {rpm: f}
        self.revMap[header[NAME]] = srpm

    def procSrc(self, f, rpm):
        self.srcPath[rpm] = f

    def getRPMS(self, src):
        """
        @return list of binary RPMS built from this source.
        """
        return [ x for x in self.rpmMap[src].itervalues() ]

    def walk(self, root):
        """
        Walk the tree rooted at root and collect information about rpms found.
        """
        ignored = ('patch.rpm', 'delta.rpm')
        for dirpath, dirnames, filenames in os.walk(root):
            for f in filenames:
                # ignore the 32-bit compatibility libs - we will
                # simply use the 32-bit components from the repository
                skip = False
                if '32bit' in f:
                    skip = True
                for suffix in ignored:
                    if f.endswith(suffix):
                        skip = True
                        break
                        continue
                if not f.endswith(".rpm"):
                    skip = True
                if skip:
                    continue
                fullpath = os.path.join(dirpath, f)
                try:
                    h = self.getHeader(fullpath)
                except IOError:
                    print 'bad rpm:', fullpath
                    os.unlink(fullpath)
                    continue
                if h[VERSION] not in f:
                    # ignore files like aaa_base.rpm.  We only want
                    # one version, like aaa_base-10-0.8.x86_64.rpm
                    continue
                if f.endswith(".src.rpm") or f.endswith('.nosrc.rpm'):
                    self.procSrc(fullpath, f)
                else:
                    self.procBin(fullpath, f)

    def getSrpms(self, pkglist):
        """
        Get source RPMS for a given list of binary RPM package names
        """
        srpms = list()
        for p in pkglist:
            srpms.append(self.revMap[p])
        return srpms

    def transformName(self, name):
        """
        In name, - => _, + => _plus.
        """

        return name.replace('-', '_').replace('+', '_plus')

    def quoteSequence(self, seq):
        """
        [a, b] => 'a', 'b'
        """

        return ', '.join("'%s'" % x for x in sorted(seq))

    def getArchs(self, src):
        """
        @return list that goes into the archs line in the recipe.
        """

        hdrs = [ self.getHeader(x) for x in self.rpmMap[src].itervalues() ]
        archs = set(h[ARCH] for h in hdrs)
        if 'i586' in archs and 'i686' in archs:
            # remove the base arch if we have an extra arch
            arch, extra = self.getExtraArchs(src)
            if arch == 'i686':
                archs.remove('i586')
        return archs

    def getNames(self, src):
        """
        @return list that goes into the rpms line in the recipe.
        """

        hdrs = [ self.getHeader(x) for x in self.rpmMap[src].itervalues() ]
        names = set(h[NAME] for h in hdrs)
        return names

    def getExtraArchs(self, src):
        """
        For the special case of RPMs that have components optimized for the
        i686 architecture while other components are at i586, then return
        ('i686', set(rpms that are i686 only)), otherwise return (None, None).
        """

        hdrs = [ self.getHeader(x) for x in self.rpmMap[src].itervalues() ]
        archMap = {}
        for h in hdrs:
            arch = h[ARCH]
            name = h[NAME]
            if arch in archMap:
                archMap[arch].add(name)
            else:
                archMap[arch] = set((name,))
        if 'i586' in archMap and 'i686' in archMap:
            if archMap['i586'] != archMap['i686']:
                return 'i686', archMap['i686']
        return None, None

    def createTemplate(self, src):
        """
        @return the content of the new recipe.
        """

        srchdr = self.getHeader(self.srcPath[src])
        l = []
        a = l.append
        a("loadSuperClass('rpmimport.recipe')")
        a('class %s(RPMImportRecipe):' %(self.transformName(srchdr[NAME])))
        a("    name = '%s'" %(srchdr[NAME]))
        a("    version = '%s_%s'" %(srchdr[VERSION], srchdr[RELEASE]))
        archs = self.getArchs(src)
        names = self.getNames(src)
        extras = self.getExtraArchs(src)[1]
        a('    rpms = [ %s ]' % self.quoteSequence(names))
        a('    archs = [ %s ]' % self.quoteSequence(archs))
        if extras:
            a("    extraArch = { 'i686': [ %s ] }" %self.quoteSequence(extras))
        # add a trailing newline
        a('')
        return '\n'.join(l)

    def createManifest(self, srpm, prefix):
        """
        @return the text for the manifest file.
        """
        l = []
        l.append(self.srcPath[srpm])
        l.extend([x for x in self.getRPMS(srpm)])
        if prefix:
            l = [ x[len(prefix):] for x in l]
        # add a trailing newline
        return '\n'.join(sorted(l) + [''])
