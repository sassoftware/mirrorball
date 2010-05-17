#
# Copyright (c) 2009 rPath, Inc.
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
This module is here as an example of the data model and interfaces that
mirrorball is looking for when importing and updating platforms in advisory
order. These are not meant as superclasses for any sort of implementation. The
variables and methods that are defined below must be available.
"""

def reqfetch(func):
    """
    Decorator to make sure manager data is loaded before a method is called.
    """

    def wrap(self, *args, **kwargs):
        if not self._fetched:
            self.fetch()
        return func(self, *args, **kwargs)
    return wrap


class Package(object):
    """
    Class to represent a package.

    @param channels: List of channel objects that this package can be found in.
    @type channels: list(Repository, ...)
    """

    def __init__(self, channels):
        for ch in channels:
            assert isinstance(ch, Channel)

        self.channels = channels

    def getNevra(self):
        """
        Returns a tuple of (name, epoch, version, release, arch) for
        this package.
        """

        raise NotImplementedError


class Channel(object):
    """
    Class to represent a repository.

    @param label: Unique key for the name of a repository.
    @type label: str
    """

    def __init__(self, label):
        self.label = label


class Advisory(object):
    """
    Class to represent an errata or advisory.

    @param issue_date: Date the advisory was issued in the following format.
                       (format characters are defined in the python time
                        module). '%Y-%m-%d %H:%M:%S'
    @type issue_date: str
    @param packages: List of package objects.
    @type packages: list(Package, ...)
    @param advisory: Unique key for the advisory
    @type advisory: str
    @param synopsis: Brief description of the advisory.
    @type synopsis: str
    """

    def __init__(self, advisory, synopsis, issue_date, packages):
        self.advisory = advisory
        self.synposis = synopsis
        self.issue_date = issue_date

        for pkg in packages:
            assert isinstance(pkg, Package)

        self.packages = packages


class AdvisoryManager(object):
    """
    Class to provide an interface for accessing advisory information for a
    platform that can then be matched up to a package source.
    """

    def getRepositories(self):
        """
        Returns a list of repository labels that have been fetched.
        """

        raise NotImplementedError

    def iterByIssueDate(self):
        """
        Yields Errata objects by the issue date of the errata.
        """

        raise NotImplementedError

    def fetch(self):
        """
        Retrieve all required advisory data.

        This is probably going to cache any data, probably in a database, that
        is being fetched from the internet somewhere so that we don't cause
        excesive load for anyone's servers.
        """

        raise NotImplementedError

    def getChannels(self):
        """
        Return a list of all indexed channels, will trigger a fetch if needed.
        """

        raise NotImplementedError

    def cleanup(self):
        """
        Frees any cached results.
        """

        raise NotImplementedError

    def getModifiedErrata(self, updateId):
        """
        Get a list of any errata that were modified after updateId and were
        issued before updateId.
        """

        raise NotImplementedError
