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

"""
Artifactor errors
"""


class ArtifactoryError(Exception):
    """
    Base Artifactory error
    """

    _params = []
    _template = "An unkown error has occured"

    def __init__(self, **kwargs):
        super(ArtifactoryError, self).__init__()

        self._kwargs = kwargs

        for key in self._params:
            setattr(self, key, kwargs[key])

    def __str__(self):
        return self._template % self.__dict__

    def __repr__(self):
        params = ', '.join('%s=%r' % x for x in self._kwargs.items())
        return '%s(%s)' % (self.__class__, params)


class MissingProjectError(ArtifactoryError):
    """Raised when a required pom file is missing from the repository"""

    _params = ['project']
    _template = '%(project)s'
