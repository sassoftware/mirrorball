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

'''
Wrappers around conary.rpmhelper.
'''

import urllib2

from conary import rpmhelper

class _SeekableStream(object):
    '''
    File like object that can be seeked forward.
    '''

    def __init__(self, url):
        self._url = url

        self._fh = urllib2.urlopen(url)
        self._pos = 0

    def read(self, *args):
        '''
        Wrapper around urllib's file object's read method that keeps track
        of position.
        '''

        buf = self._fh.read(*args)
        self._pos += len(buf)
        return buf

    def seek(self, amount, sense):
        '''
        Simple seek implementation that only goes forward.
        @param amount: amount to seek into file.
        @type amount: integer
        @param sense: direction to seek into file (only valid value is 1)
        @type sense: integer
        '''

        assert(sense == 1)
        self.read(amount)

    def tell(self):
        '''
        Report the current position in the file.
        @return current position in the file
        '''

        return self._pos


def readHeader(url):
    '''
    Read an RPM header (and only the RPM header) from a remotely hosted RPM.
    @param url: url to RPM file.
    @type url: string
    @return conary.rpmhelper.RpmHeader object
    '''

    fh = _SeekableStream(url)

    # Have to read into the file a bit to get to the begining of the header
    # that we care about.
    fh.read(96)
    rpmhelper.RpmHeader(fh)

    header = rpmhelper.RpmHeader(fh)
    return header
