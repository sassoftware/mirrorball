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
