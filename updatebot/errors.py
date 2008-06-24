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


class UnhandledUpdateError(UpdateBotError):
    """
    UnhandledUpdateError, raised when the bot finds a state that it does not
    know how to handle.
    """

    _params = ['why']
    _template = 'An unhandled update case has occured: %(why)s'


class TooManySrpmsError(UnhandledUpdateError):
    """
    TooManySrpmsError, raised when the bot finds multiple srpms of the same
    version.
    """

class UpdateGoesBackwardsError(UnhandledUpdateError):
    """
    UpdateGoesBackwardsError, raised when the bot tries to update to an older
    version.
    """

class UpdateRemovesPackageError(UnhandledUpdateError):
    """
    UpdateRemovesPackageError, raised when the bot tries to remove an rpm from
    the manifest.
    """

class TooManyFlavorsFoundError(UnhandledUpdateError):
    """
    TooManFlavorsFoundError, raised when the bot finds more flavors of the top
    level group trove than expected.
    """

class NoManifestFoundError(UnhandledUpdateError):
    """
    NoManifestFoundError, raised when the bot checks out a source component
    and doesn't find a manifest file.
    """

    _params = ['pkgname', 'dir']
    _template = 'No manifest was found for %(pkgname)s in directory %(dir)s'

class PromoteFailedError(UnhandledUpdateError):
    """
    PromoteFailedError, raised when the bot fails to promote the binary group
    to the target release label.
    """

    _params = ['what']
    _template = 'Failed to promote %(what)s'

class PromoteMismatchError(PromoteFailedError):
    """
    PromoteMismatchError, raised when the promote to the production label
    either tries to promote packages that are unexpected or does not
    promote all expected pacakges.
    """

    _params = ['expected', 'actual']
    _template = ('Expected to promote %(expected)s, actually tried to promote'
                 ' %(actual)s.')

class AdvisoryError(UnhandledUpdateError):
    """
    Base error for other advisory errors to inherit from.
    """

    _template = 'An advisory error has occured: %(why)s'

class NoAdvisoryFoundError(AdvisoryError):
    """
    NoAdvisoryFoundError, raised when the bot can not find an advisory for an
    updated package.
    """

class ProductNameNotDefinedError(AdvisoryError):
    """
    ProductNameNotDefinedError, raised when the product name is not defined
    in the config.
    """

    _params = []
    _template = 'Product name not defined'

class NoSenderFoundError(AdvisoryError):
    """
    NoSenderFoundError, raised when no sender is defined in the config file.
    """

    _template = 'No sender defined for advisory emails: %(why)s'

class NoRecipientsFoundError(AdvisoryError):
    """
    NoRecipientsFoundError, raised when no recipients are defined in the
    config file.
    """

    _template = 'No recipients defined for advisory emails: %(why)s'

class FailedToSendAdvisoryError(AdvisoryError):
    """
    FailedToSendAdvisoryError, raised when the smtp server fails to send the
    advisory.
    """

    _params = ['error', ]
    _template = 'Failed to send advisory: %(error)s'

class AdvisoryRecipientRefusedError(FailedToSendAdvisoryError):
    """
    AdvisoryRecipientRefusedError, raised when the smtp server refuses one or
    more recipients, but not all of them.
    """

    _params = ['data', ]
    _template = ('One or more recipients was refused by the smtp server: '
                 '%(data)s')

class NoPackagesFoundForAdvisory(AdvisoryError):
    """
    NoPackagesFoundForAdvisory, raised when the bot can't find promoted
    binary versions of a package.
    """

    _params = ['what', ]
    _template = 'Could not find binary packages for %(what)s'

class MultipleAdvisoriesFoundError(AdvisoryError):
    """
    MultipleAdvisoriesFoundError, raised when multiple advisories are found
    for one source.
    """

    _params = ['what', 'advisories']
    _template = 'Found multiple advisories for %(what)s: %(advisories)s'
