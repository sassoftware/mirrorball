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
PackageSource Errors Module
"""

from updatebot.errors import UpdateBotError

class PackageSourceError(UpdateBotError):
    """
    Base error for all package source related errors to inherit from.
    """

class UnsupportedRepositoryError(PackageSourceError):
    """
    Raised when an unsupported backend is used.
    """

    _params = ['repo', 'supported']
    _template = ('%(repo)s is not a supported repository format, please '
                 'choose one of the following %(supported)s')
