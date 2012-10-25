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
