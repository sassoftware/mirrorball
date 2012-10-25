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
