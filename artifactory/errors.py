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

    _template = None

    def __init__(self, *args, **kwargs):
        if self._template is None:
            super(ArtifactoryError, self).__init__(*args, **kwargs)
        else:
            super(ArtifactoryError, self).__init__(
                self._template.format(*args, **kwargs))


class MissingProjectError(ArtifactoryError):
    """Raised when a required pom file is missing from the repository"""

    _template = 'Missing pom: {0}'


class MissingArtifactError(ArtifactoryError):
    """Raised when a required artifact file is missing from the repository"""

    _template = 'No such file found: {0}'
