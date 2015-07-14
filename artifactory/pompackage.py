#
# Copyright (c) 2014 SAS Institute Inc
#

import logging

from pymaven import errors as merrors
from pymaven.pom import Pom

from . import errors


log = logging.getLogger(__name__)


class PomPackage(Pom):
    """Abstracts away processing pom xml
    """
    __slots__ = ('location', '_cache', '_artifacts')

    def __init__(self, coordinate, location, client, cache):
        """
        Create a PomPackage

        :param str coordinate: pom coordinate
        :param location: location string
        :type location: str
        :param parent: parent project
        :type parent: PomPackage or None
        :param artifacts: artifacts associated with this project
        :type artifacts: list of json objects or None
        :param arch: architecture string
        :type arch: str or None
        """
        super(PomPackage, self).__init__(coordinate, client)
        self.location = location
        self._cache = cache
        self._artifacts = None

    def __repr__(self):
        return '<pomsource.Package(%r, %r, %r)>' % (self.coordinate,
                                                    self._client, self._cache)

    def __str__(self):
        return self.coordinate

    def _pom_factory(self, *gav):
        if self._cache is not None and gav in self._cache:
            return self._cache[gav]

        log.info("Creating pom package for %s:%s:%s", *gav)
        location = self._client.constructPath(*gav)
        location = self._client.checkPath(location)
        if location is None:
            raise errors.MissingProjectError(':'.join(gav))

        log.debug("Found pom at %s", location)
        try:
            pom = PomPackage("%s:%s:pom:%s" % gav, location, self._client,
                             self._cache)
            if self._cache is not None:
                self._cache[gav] = pom
        except merrors.MissingArtifactError:
            if self._cache is not None and gav in self._cache:
                del self._cache[gav]
                raise errors.MissingProjectError(':'.join(gav))
        return pom

    @property
    def arch(self):
        return "x86_64"

    @property
    def artifacts(self):
        if self._artifacts is None:
            gavc = self.getGAV()
            self._artifacts = [dict(
                downloadUri=self._client.artifactUrl(*gavc),
                path=self._client.constructPath(*gavc),
                )]
            if self._client.checkJar(*gavc):
                self._artifacts.append(dict(
                    downloadUri=self._client.artifactUrl(*gavc, extension='jar'),
                    path=self._client.constructPath(*gavc, extension='jar'),
                    ))
        return self._artifacts
    @property
    def checksum(self):
        return None

    @property
    def epoch(self):
        return '0'

    @property
    def buildRequires(self):
        return sorted([d.name for d in self.dependencies])

    @property
    def release(self):
        return ''

    def getConaryVersion(self):
        assert self.version.version is not None
        return str(self.version.version).replace('-', '_')

    def getGAV(self):
        return self.group_id, self.artifact_id, self.version

    def getNevra(self):
        return self.name, self.epoch, self.version, self.release, self.arch

    @property
    def name(self):
        return str("__".join([self.group_id, self.artifact_id]))

    @property
    def nevra(self):
        return self

    def pick_version(self, spec, artifacts):
        """Pick a version from *versions* according to the spec

        If spec contains a '+', then it is a gradle dyanmic version, and we
        return the newest version in `availableVersions` that starts with
        `spec`.

        Otherwise, convert spec into maven version range and return the first
        version in *versions* that is within the range.

        :param str spec: a maven version range spec or gradle dynamic version
        :param versions: list of available versions for this artifact
        :type versions: [:py:class:`pymaven.Version`, ...]
        :return: the newest version that matches the spec
        :rtype: str or None
        """
        if '+' in spec:
            # this is a gradle dynamic version
            for artifact in artifacts:
                if str(artifact.version).startswith(spec[:-1]):
                    return str(artifact.version)
        else:
            return super(PomPackage, self).pick_version(spec, artifacts)
