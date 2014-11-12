#
# Copyright (c) 2014 SAS Institute Inc
#

import logging


log = logging.getLogger(__name__)


class Package(object):
    __slots__ = ('artifacts', 'arch', 'fullVersion', 'name', 'buildRequires',
                 'epoch', 'version', 'release', 'location',)

    def __init__(self, pom, location, arch='src', artifacts=None):
        self.location = location
        self.arch = arch and arch or ''
        self.artifacts = artifacts
        self.epoch = '0'

        try:
            self.fullVersion = str(pom.version).strip()
        except AttributeError:
            log.debug("No version set, trying parent project")
            self.fullVersion = str(pom.parent.version).strip()

        self.name = str(pom.artifactId)

        head, _, tail = self.fullVersion.rpartition('-')
        if head and tail:
            self.version = head.replace('-', '_')
            self.release = tail.replace('-', '_')
        elif tail:
            self.version = tail.replace('-', '_')
            self.release = ''
        else:
            raise ValueError("Could not parse maven version into"
                             " version and release")

        self.buildRequires = self._getBuildRequires(pom)

    def __repr__(self):
        return '<pomsource.Package(%r, %r, %r)>' % (
            self.name, self.version, self.arch)

    def getConaryVersion(self):
        assert self.arch == 'src'
        return self.fullVersion.replace('-', '_')

    def _getBuildRequires(self, pom):
        buildRequires = set()
        if hasattr(pom, 'parent'):
            # add parent projects as a build req
            buildRequires.add(str(pom.parent.artifactId))

        if hasattr(pom, 'dependencies'):
            for dep in pom.dependencies.iterchildren():
                if hasattr(dep, 'optional') and dep.optional:
                    # ignore opitonal deps, these are deps a dependent
                    # project may want to include
                    continue

                if hasattr(dep, 'scope') and str(dep.scope) != 'compile':
                    # we only want compile deps (the default)
                    continue

                buildRequires.add(str(dep.artifactId))

        return buildRequires

    def getNevra(self):
        return self.name, self.epoch, self.version, self.release, self.arch

    @property
    def nevra(self):
        return self

    @property
    def checksum(self):
        return None
