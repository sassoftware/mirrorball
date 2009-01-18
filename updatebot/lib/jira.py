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
Module for manipulating Jira issues.
"""

import pyjira

class JiraClient(pyjira.JiraClient):
    """
    Basic SOAP based Jira client.
    """

    def __init__(self, cfg):
        self._cfg = cfg
        self._wsdl = '%s/rpc/soap/jirasoapservice-v2?wsdl' % self._cfg.jiraUrl
        self._login = (self._cfg.jiraUser, self._cfg.jiraPassword)

        pyjira.JiraClient.__init__(self, self._wsdl, self._login)

    def addComment(self, issueKey, body):
        """
        Add a comment to an issue, using the security level specified in the
        config object.
        """

        pyjira.JiraClient.addComment(self, issueKey, body,
            level=self._cfg.jiraSecurityGroup)
