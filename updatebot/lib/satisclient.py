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
