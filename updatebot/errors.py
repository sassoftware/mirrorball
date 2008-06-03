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
UpdateBot specific errors.
"""

class UpdateBotError(Exception):
    """
    Base UpdateBot Error for all other errors to inherit from.
    """

    _params = []
    _template = 'An unknown error has occured.'

    def __init__(self, **kwargs):
        Exception.__init__(self)

        self._kwargs = kwargs

        # Copy kwargs to attributes
        for key in self._params:
            setattr(self, key, kwargs[key])

    def __str__(self):
        return self._template % self.__dict__

    def __repr__(self):
        params = ', '.join('%s=%r' % x for x in self._kwargs.iteritems())
        return '%s(%s)' % (self.__class__, params)


class CommitFailedError(UpdateBotError):
    """
    CommitFailedError, raised when failing to commit to a repository.
    """

    _params = ['jobId', 'why']
    _template = 'rMake job %(jobId)d failed to commit: %(why)s'


class JobFailedError(UpdateBotError):
    """
    JobFailedError, raised when an rMake job fails.
    """

    _params = ['jobId', 'why']
    _templates = 'rMake job %(jobId)s failed: %(why)s'
