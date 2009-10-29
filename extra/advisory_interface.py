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


class Package(object):
    """
    Class to represent a package.
    """

    # List of channel objects that this package can be found in.
    channels = [ Channel ]

    def getNevra(self):
        """
        Returns a tuple of (name, epoch, version, release, arch) for
        this package.
        """

class Repository(object):
    """
    Class to represent a repository.
    """

    # Unique key for the name of a repository.
    label = str


class Advisory(object):
    """
    Class to represent an errata or advisory.
    """

    # Date the advisory was issued in the following format. (format characters
    # are defined in the python time module). '%Y-%m-%d %H:%M:%S'
    issue_date = str

    # List of package objects.
    packages = [ Package ]

    # Unique key for the advisory
    advisory = str

    # Brief description of the advisory.
    synopsis = str

class AdvisoryManager(object):
    def getRepositories(self):
        """
        Returns a list of repository labels that have been fetched.
        """

    def iterByIssueDate(self):
        """
        Yields Errata objects by the issue date of the errata.
        """

    def fetch(self):
        """
        Retrieve all required advisory data.

        This is probably going to cache any data, probably in a database, that
        is being fetched from the internet somewhere so that we don't cause
        excesive load for anyone's servers.
        """
