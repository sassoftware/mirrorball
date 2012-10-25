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
