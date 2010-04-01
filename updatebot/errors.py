#
# Copyright (c) 2008-2010 rPath, Inc.
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
    _template = 'rMake job %(jobId)s failed to commit: %(why)s'


class FailedToRetrieveChangesetError(CommitFailedError):
    """
    FailedToRetrieveChangesetError, 
    """

    _template = 'Failed to fetch changeset contents for job %(jobId)s: %(why)s'


class ChangesetValidationFailedError(CommitFailedError):
    """
    ChangesetValidationFailedError, raised when the builder fails to validate
    the built changeset.
    """

    _params = ['jobId', 'reason']
    _template = ('Changeset from rmake job %(jobId)s failed to pass '
        'validation because:\n%(reason)s')


class JobFailedError(UpdateBotError):
    """
    JobFailedError, raised when an rMake job fails.
    """

    _params = ['jobId', 'why']
    _template = 'rMake job %(jobId)s failed: %(why)s'


class JobNotCompleteError(UpdateBotError):
    """
    JobNotCompleteError, raised when the build dispatcher thinks that the job
    should be done, but it isn't.
    """

    _params = ['jobId', ]
    _template = 'Build job not complete %(jobId)s'


class UnhandledKernelModule(UpdateBotError):
    """
    UnhandledKernelModule, raised when trying to create a build job with a
    package that looks as if it might be a kernel module that does not have
    special flavors definied.
    """

    _param = ['name', ]
    _template = ('Attempted to create build job containing %(name)s, which '
        'appears to be a kernel module, without kernel flavors defined. Please '
        'define the set of flavors this kernel module should be built in.')


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

class OldVersionNotFoundError(UnhandledUpdateError):
    """
    OldVersionNotFoundError, raised when the bot can not find metadata for
    the current versionoof a package.
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
    _params = ['pkgList', 'pkgNames',
               'oldspkg', 'newspkg',
               'oldNevra', 'newNevra']
    _template = '%(pkgList)s removed going from %(oldNevra)s to %(newNevra)s'

class UpdateReusesPackageError(UnhandledUpdateError):
    """
    UpdateReusesPackageError, raised when the bot tries to use an old
    package with a newer srpm.
    """
    _params = ['pkgList', 'pkgNames',
               'oldspkg', 'newspkg',
               'oldNevra', 'newNevra']
    _template = '%(pkgList)s reused going from %(oldNevra)s to %(newNevra)s'

class GroupNotFound(UnhandledUpdateError):
    """
    GroupNotFound, raised when the bot can't find the top level group as
    configured.
    """

    _params = ['group', 'label']
    _template = 'Could not find %(group)s on label %(label)s'

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

class NoCheckoutFoundError(UnhandledUpdateError):
    """
    NoCheckoutFoundError, raised when trying to commit a package that has not
    been checked out.
    """

    _params = ['pkgname']
    _template = 'No checked out version of %(pkgname)s was found.'

class BinariesNotFoundForSourceVersion(UnhandledUpdateError):
    """
    BinariesNotFoundForSourceVersion, raised when querying by source name and
    version for all binaries build from the given source version. Normally means
    that an incorrect source name and/or version was provided or the source was
    never built.
    """

    _params = ['srcName', 'srcVersion', ]
    _template = 'Can not find binaries for %(srcName)s=%(srcVersion)s'

class RepositoryPackageSourceInconsistencyError(UnhandledUpdateError):
    """
    RepositoryPackageSourceInconsistencyError, raised when the manifest for a
    given source component does not match the state of the package source. This
    should only be triggered when the upstream provider of updates has gone back
    and changed the package set for an update that has already been imported
    into the conary repository.
    """

    _params = ['nvf', 'srpm', ]
    _template = ('An inconsistency has been discovered between the conary '
        'repository contents and the upstream package source for %(srpm)s. '
        'This is normally due to upstream modifying the package set for an '
        'update that has already been imported into the conary repository.')

class ParentPlatformManifestInconsistencyError(UnhandledUpdateError):
    """
    ParentPlatformManifestInconsistencyError, raised when the manifest contents
    that would be generated by the platform package source differs from the
    upstream platform manifest.
    """

    _params = ['srcPkg', 'manifest', 'parentManifest', ]
    _template = ('An inconsistency has been dicovered between the platform '
        'package source and the parent platform manifest for %(srcPkg)s')

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

class PromoteMissingVersionError(PromoteFailedError):
    """
    PromoteMissingVersionError, raised when ordered promote finds a group that
    should have already been promoted to the target label.
    """

    _params = ['missing', 'next']
    _template = ('Expected to find group verison %(missing)s before %(next)s '
        'on the target label.')

class PromoteFlavorMismatchError(PromoteFailedError):
    """
    PromoteFlavorMismatchError, raised when the number of flavors found to
    promote does not match the number of flavors that should have been built.
    """

    _params = ['cfgFlavors', 'troves', 'version']
    _template = ('The number of configured group flavors did not match the '
        'number of flavors found in the repository for %(version)s')

class MirrorFailedError(UnhandledUpdateError):
    """
    MirrorFailedError, raised when the mirror process fails.
    """

    _params = ['rc', ]
    _template = 'Mirror process exited with code %(rc)s'

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

class ExtraPackagesFoundInUpdateError(AdvisoryError):
    """
    ExtraPackagesFoundInUpdateError, raised when packages are found for an
    update that are not mentioned in the advisory.
    """

    _params = ['pkg', 'src', 'advisory']
    _template = ('At least one (%(pkg)s) was found that is not mentioned in the'
                 ' advisory for %(src)s, %(advisory)s')

class MultipleAdvisoriesFoundError(AdvisoryError):
    """
    MultipleAdvisoriesFoundError, raised when multiple advisories are found
    for one source.
    """

    _params = ['what', 'advisories']
    _template = 'Found multiple advisories for %(what)s: %(advisories)s'

class ErrataError(UpdateBotError):
    """
    Base exception class for errata related errors.
    """

class ErrataPackageNotFoundError(ErrataError):
    """
    ErrataPackageNotFoundError, raised when a package can not be found in the
    package source that matches a package in the errata source.
    """

    _params = ['pkg', ]
    _template = ('Could not find a matching package for %(pkg)s in the '
        'configured repositories when attempting to map errata source to '
        'package source.')

class ErrataSourceDataMissingError(ErrataError):
    """
    ErrataSourceDataMissingError, raised when missing package or channel data is
    detected. This normally means that the errata source is corupt or missing
    data.
    """

    _params = ['broken', ]
    _template = ('Found missing information when parsing errata source. This '
                 'normally means that the errat source is corrupt or incorect. '
                 '%(broken)s')

class AdvisoryPackageMissingFromBucketError(ErrataError):
    """
    AdvisoryPackageMissingFromBucketError, raised when moving advisories between
    buckets and the expected packages can not be found.
    """

    _params = ['nevra', ]
    _template = 'Failed to find %(nevra)s in source update bucket.'

class PackageNotFoundInBucketError(ErrataError):
    """
    PackageNotFoundInBucketError, raised when moving sources between buckets and
    the specified nevra can not be found in the source bucket.
    """

    _params = ['nevra', 'bucketId', ]
    _template = 'Can not find %(nevra)s in %(bucketId)s'

class GroupManagerError(UpdateBotError):
    """
    GroupManagerError, generic error for group manager related errors.
    """

    _template = 'Group manager error'

class UnsupportedTroveFlavorError(GroupManagerError):
    """
    UnsupportedTroveError, raised when the group manager runs across a flavor it
    does not know what to do with.
    """

    _params = ['name', 'flavor']
    _template = ('Do not know what to do with flavor %(flavor)s from trove '
        '%(name)s')

class UnknownBuildContextError(GroupManagerError):
    """
    UnknownBuildContextError, raised when the group manager finds a build
    context on a special package that does not match either the x86 or
    x86_64 filter.
    """

    _params = ['name', 'context']
    _template = ('Context does not fall into the x86 or x86_64 flavor sets.')

class FlavorCountMismatchError(GroupManagerError):
    """
    FlavorCountMismatchError, raised when the number of built package flavors
    does not match the configured flavors.
    """

    _params = ['name', ]
    _template = ('Could not find all built flavors for %(name)s. Maybe one of '
        'the configured contexts resulted in an overlap.')

class UnhandledPackageAdditionError(GroupManagerError):
    """
    UnhandledPackageAdditionError, raised when the group manager just doesn't
    know what to do when adding a package.
    """

    _params = ['name', ]
    _template = 'I do not know what to do with this package %(name)s.'

class UnknownPackageFoundInManagedGroupError(GroupManagerError):
    """
    UnknownPackageFoundInManagedGroupError, raised when a package is dicovered
    in one of the managed non package groups that no longer exists in the
    package group.
    """

    _params = ['what', ]
    _template = ('The following package is no longer managed as part of the '
        'version group %(what)s, you may need to remove this package from any '
        'other static group definitions.')

class NameVersionConflictsFoundError(GroupManagerError):
    """
    NameVersionConflictsFoundError, raised when multiple versions of the same
    source are referenced by binaries in a managed group.
    """

    _params = ['conflicts', 'groupName', 'binPkgs', ]
    _template = ('Multiple versions of the following sources are referenced '
                 'in %(groupName)s: %(conflicts)s')

class OldVersionsFoundError(GroupManagerError):
    """
    OldVersionsFoundError, raised when the latest source/build version of a
    package is not in a group. This happens when an old package has been
    rebuilt and has a new build count or source, but the same upstream version.
    """

    _params = ['pkgNames', 'errors', ]
    _template = 'Newer versions of $(pkgNames)s were found.'

class GroupValidationFailedError(GroupManagerError):
    """
    GroupValidationFailedError, raised when errors are discovered in validate
    the group model. Contains a reference to all errors discovered.
    """

    _params = ['errors', ]
    _template = 'Errors were discovered with the group model.'

class NotCommittingOutOfDateSourceError(GroupManagerError):
    """
    NotCommittingOutOfDateSourceError, raised when trying to commit a group
    model that is not the latest version of the source component.
    """

    _params = []
    _template = 'Can not commit out of date source.'

class ExpectedRemovalValidationFailedError(GroupManagerError):
    """
    ExpectedRemovalValidationFailedError, raised when package remove validation
    fails.
    """

    _params = ['updateId', 'pkgNames', ]
    _template = ('The following package names were not properly removed from '
                 'the group model at updateId %(updateId)s: %(pkgNames)s')

class ImportError(UpdateBotError):
    """
    General purpose error for all import related issues.
    """

class PlatformAlreadyImportedError(ImportError):
    """
    PlatformAlreadyImportedError, raised when a platform is being created in
    ordered mode that already exists.
    """

    _params = []
    _template = ('This platform has already been imported, you probably meant '
        'to run an update.')

class PlatformNotImportedError(ImportError):
    """
    PlatformNotImportedError, raised when a platform is being updated, but has
    not yet been created.
    """

    _params = []
    _template = 'This platform has not yet been created.'

class TargetVersionNotFoundError(ImportError):
    """
    TargetVersionNotFoundError, raised when a group version that is expected to
    be on the targetLabel can not be found.
    """

    _params = ['updateId', 'version']
    _template = ('Could not find %(version)s of the top level group on '
        'targetLabel')

class CvcError(UpdateBotError):
    """
    Generic cvc related error.
    """

    _params = []
    _template = 'cvc failed'

class LocalCookFailedError(CvcError):
    """
    LocalCookFailedError, raised when cvc.cook fails.
    """

    _parms = ['troveSpecs', ]
    _template = 'Failed while cooking %(troveSpecs)s'

class PackageSourceError(UpdateBotError):
    """
    Generic error for all package source errors to decend from.
    """

    _parms = []
    _template = 'an error has occured in the package source'

class CanNotFindSourceForBinariesError(PackageSourceError):
    """
    CanNotFindSourceForBinariesError, raise when synthesizing sources and the
    binary package has a source of a different name and a source of that name,
    version, and release can not be found.
    """

    _params = ['count', ]
    _template = ('Could not find %(count) sources for matching binary '
        'packages. This generally means that there is a binary package with a '
        'source of a different name and a source can not be found with a '
        'matching source name, version, and release.')

class ErrataFilterError(UpdateBotError):
    """
    Generic errata filter error.
    """

    _params = []
    _template = 'generic errata filter error'

class UnableToMergeUpdatesError(ErrataFilterError):
    """
    UnableToMergeUpdatesError, raised when errata buckets can not be merged
    together.
    """

    _params = [ 'source', 'target', 'package', ]
    _template = ('Can not merge %(source)s into %(target)s due to conflicting '
                 'package %(package)s')

class MissingErrataError(ErrataFilterError):
    """
    MissingErrataError, raised when packages are discovered without an
    associated errata.
    """

    _params = [ 'packages', ]
    _template = 'The following packages do not have an errata: %(packages)s'

class ConfigurationError(UpdateBotError):
    """
    Generic exception class for configuration related errors.
    """

    _params = []
    _template = 'An error has been discovered with your configuration.'

class UnknownRemoveSourceError(ConfigurationError):
    """
    UnknownRemoveSourceError, raised when an unknown source nevra is specified
    in the removeSource directive in the updatebotrc.
    """

    _params = ['nevra', ]
    _template = ('The following source nevra, mentioned in a removeSource line '
                 'in your config, was not found: %(nevra)s')
