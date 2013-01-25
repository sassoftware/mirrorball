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
Wrappers around conary.rpmhelper.
"""

import urllib2

from conary import rpmhelper

class SeekableStream(object):
    """
    File like object that can be seeked forward.
    """

    def __init__(self, url):
        self._url = url

        self._fh = urllib2.urlopen(url)
        self._pos = 0

    def read(self, *args):
        """
        Wrapper around urllib's file object's read method that keeps track
        of position.
        """

        buf = self._fh.read(*args)
        self._pos += len(buf)
        return buf

    def seek(self, amount, sense):
        """
        Simple seek implementation that only goes forward.
        @param amount: amount to seek into file.
        @type amount: integer
        @param sense: direction to seek into file (only valid value is 1)
        @type sense: integer
        """

        assert(sense == 1)
        self.read(amount)

    def tell(self):
        """
        Report the current position in the file.
        @return current position in the file
        """

        return self._pos

    def getTotalSize(self):
        """
        Return the size in the header.
        @return content length
        """

        return int(self._fh.headers.getheader('content-length'))

def readHeader(url):
    """
    Read an RPM header (and only the RPM header) from a remotely hosted RPM.
    @param url: url to RPM file.
    @type url: string
    @return conary.rpmhelper.RpmHeader object
    """

    fh = SeekableStream(url)
    header = rpmhelper.RpmHeader(fh)
    return header
