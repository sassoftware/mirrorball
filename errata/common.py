#
# Copyright (c) rPath, Inc.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#


"""
This module is here as an example of the data model and interfaces that
mirrorball is looking for when importing and updating platforms in advisory
order. The variables and methods that are defined below must be available.
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


class Nevra(object):
    """
    Class to represent a package nevra.
    """

    __slots__ = ('name', 'epoch', 'version', 'release', 'arch', )

    def __init__(self, name, epoch, version, release, arch):
        self.name = name
        self.epoch = epoch
        self.version = version
        self.release = release
        self.arch = arch

    def getNevra(self):
        """
        Return a tuple representation of the nevra.
        """

        return (self.name, self.epoch, self.version, self.release, self.arch)


class Package(object):
    """
    Class to represent a package.

    @param channels: List of channel objects that this package can be found in.
    @type channels: list(Repository, ...)
    """

    __slots__ = ('channel', 'nevra', )

    def __init__(self, channel, nevra):
        assert isinstance(channel, Channel)
        assert isinstance(nevra, Nevra)

        self.channel = channel
        self.nevra = nevra

    def getNevra(self):
        """
        Returns a tuple of (name, epoch, version, release, arch) for
        this package.
        """

        return self.nevra.getNevra()


class Channel(object):
    """
    Class to represent a repository.

    @param label: Unique key for the name of a repository.
    @type label: str
    """

    __slots__ = ('label', )

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

    __slots__ = ('advisory', 'synopsis', 'issue_date', 'nevraChannels', )

    def __repr__(self):
        return self.advisory

    def __init__(self, advisory, synopsis, issue_date, packages):
        self.advisory = advisory
        self.synopsis = synopsis
        self.issue_date = issue_date

        for pkg in packages:
            assert isinstance(pkg, Package)

        self.nevraChannels = packages

    def __hash__(self):
        return hash((self.advisory, self.synopsis, self.issue_date))

    def __cmp__(self, other):
        return cmp((self.issue_date, self.advisory, self.synopsis),
                   (other.issue_date, other.advisory, other.synopsis))


class AdvisoryManager(object):
    """
    Class to provide an interface for accessing advisory information for a
    platform that can then be matched up to a package source.
    """

    def __init__(self):
        self._fetched = False

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
