#
# Copyright (c) 2008 rPath, Inc.
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
