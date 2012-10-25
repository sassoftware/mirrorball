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
Module for interacting with satis.
"""

from satis import types
from satis.types import And, Equals
from satis import util as satisutil
from satis.client.http import HTTPClient

class SatisClient(object):
    """
    Base class for interacting with satis.
    """

    def __init__(self, url):
        self._url = url
        self._client = HTTPClient(self._url)


class AutoBuild(SatisClient):
    """
    Class for managing autobuild related metadata in satis.
    """

    def __init__(self, url, productName):
        SatisClient.__init__(self, url)
        self._productName = productName
        self._type = 'com.rpath.autobuild.checkdata'

    def setUUID(self, label, uuid):
        """
        Set autobuild checkdata.
        """

        symb = types.Symbol()
        symb['type'] = self._type
        symb['autobuild-symbol-version'] = 0
        symb['autobuild-product-name'] = self._productName
        symb['autobuild-label'] = label.asString()
        symb['autobuild-check-uuid'] = uuid
        self._client.add(symb)

    def getUUID(self, label):
        """
        Get the last checkdata for a given label.
        """

        matcher = And(Equals('type', self._type),
                      Equals('autobuild-label', label.asString()),
                      Equals('autobuild-product-name', self._productName))
        fltr = types.Filter(matcher, order=types.ORDER_DESC, limit=1)
        sub = types.Subscription(fltr)
        req = self._client.subscribe(sub)

        if req:
            return req[0].symbol['autobuild-check-uuid']
        return satisutil.makeUUID()


class ConaryCommits(SatisClient):
    """
    Interface for searching satis for commits to a given label.
    """

    def __init__(self, url, productName):
        SatisClient.__init__(self, url)
        self._rules = ( Equals('type', 'com.rpath.commit.conary.trove'),
                        Equals('trove-type', 'source') )
        self._autobuild = AutoBuild(self._url, productName)

    def search(self, label, getMarked=False):
        """
        Query satis for commits to the given label.
        @param label: conary label
        @type label: conary.versions.Label
        @param getMarked: to return all commits or just the commits since the
                          last check.
        @type getMarked: boolean
        """

        uuid = self._autobuild.getUUID(label)

        rules = list(self._rules)
        rules.append(Equals('trove-label', label.asString()))
        matcher = And(*rules)

        fltr = types.Filter(matcher, order=types.ORDER_ASC, token=uuid,
                            getMarked=getMarked)
        sub = types.Subscription(fltr, token=uuid, markOnSend=True)
        req = self._client.subscribe(sub)

        self._autobuild.setUUID(label, uuid)
        return req
