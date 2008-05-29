#!/usr/bin/python
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

import testsetup

import mock
import slehelp

from rmake.cmdline import monitor, commit

from updatebot import build
from updatebot import errors

class BuilderTest(slehelp.Helper):
    def _getBuilder(self):
        mockJob = mock.MockObject(stableReturnValues=True)
        mockJob.isFailed._mock.setReturn(False)
        mockJob.isFinished._mock.setReturn(False)
        mockJob.iterBuiltTroves._mock.setReturn([])
        mockHelper = mock.MockObject(stableReturnValues=True)
        mockHelper.createBuildJob._mock.setReturn(mockJob)
        mockHelper.buildJob._mock.setReturn(1)
        mockHelper.getJob._mock.setReturn(mockJob)
        builder = build.Builder(self.updateBotCfg)


    def testStartJob(self):
        trvSpecs = (('foo', '', ''), )

        mockJob = mock.MockObject()
        mockHelper = mock.MockObject(stableReturnValues=True)
        mockHelper.createBuildJob._mock.setReturn(mockJob, trvSpecs)
        mockHelper.buildJob._mock.setReturn(1, mockJob)

        builder = build.Builder(self.updateBotCfg)
        builder._helper = mockHelper
        jobId = builder._startJob(trvSpecs)

        mockHelper.createBuildJob._mock.assertCalled(trvSpecs)
        mockHelper.buildJob._mock.assertCalled(mockJob)
        self.failUnlessEqual(jobId, 1)

    def testMonitorJob(self):
        mockMonitor = mock.MockObject()
        self.mock(monitor, 'monitorJob', mockMonitor)

        builder = build.Builder(self.updateBotCfg)
        builder._monitorJob(1)

        mockMonitor._mock.assertCalled(builder._helper.client, 1,
            exitOnFinish=True, displayClass=build._StatusOnlyDisplay)

    def testSanityCheckJob(self):
        jobId = 1

        mockJob = mock.MockObject(stableReturnValues=True)
        mockHelper = mock.MockObject(stableReturnValues=True)
        mockHelper.getJob._mock.setReturn(mockJob, jobId)

        builder = build.Builder(self.updateBotCfg)
        builder._helper = mockHelper

        mockJob.isFailed._mock.setReturn(True)
        self.failUnlessRaises(errors.JobFailedError, builder._sanityCheckJob, jobId)
        mockHelper.getJob._mock.assertCalled(jobId)
        mockJob.isFailed._mock.assertCalled()
        mockJob.isFinished._mock.assertNotCalled()
        mockJob.iterBuiltTroves._mock.assertNotCalled()
        mockJob.isFailed._mock.setReturn(False)

        mockJob.isFinished._mock.setReturn(False)
        self.failUnlessRaises(errors.JobFailedError, builder._sanityCheckJob, jobId)
        mockHelper.getJob._mock.assertCalled(jobId)
        mockJob.isFailed._mock.assertCalled()
        mockJob.isFinished._mock.assertCalled()
        mockJob.iterBuiltTroves._mock.assertNotCalled()
        mockJob.isFinished._mock.setReturn(True)

        mockJob.iterBuiltTroves._mock.setReturn([])
        self.failUnlessRaises(errors.JobFailedError, builder._sanityCheckJob, jobId)
        mockHelper.getJob._mock.assertCalled(jobId)
        mockJob.isFailed._mock.assertCalled()
        mockJob.isFinished._mock.assertCalled()
        mockJob.iterBuiltTroves._mock.assertCalled()
        mockJob.iterBuiltTroves._mock.setReturn([1, 2, 3])

    def testCommitJob(self):
        jobId = 1

        sampleData = {'foo': {
                        ('foo', '1.0', 'is:x86'): [
                            ('foo:source', '1.0-1', ''),
                            ('foo:config', '1.0-1-1', 'is:x86'),
                            ('foo:runtime', '1.0-1-1', 'is:x86'), ]
                        },
                      'bar': {
                        ('bar', '1.0', 'is:x86_64'): [
                            ('bar:source', '1.0-1', ''),
                            ('bar:runtime', '1.0-1-1', 'is:x86_64'), ]
                        },
                     }

        expected = {}
        for value in sampleData.itervalues():
            for buildTrove, committedTrove in value.iteritems():
                expected[buildTrove] = committedTrove

        mockJob = mock.MockObject(stableReturnValues=True)
        mockHelper = mock.MockObject(stableReturnValues=True)
        mockHelper.getJob._mock.setReturn(mockJob, jobId)
        mockCommitJobs = mock.MockObject(stableReturnValues=True)

        self.mock(commit, 'commitJobs', mockCommitJobs)

        builder = build.Builder(self.updateBotCfg)
        builder._helper = mockHelper

        mockCommitJobs._mock.setDefaultReturn((True, sampleData))
        trvMap = builder._commitJob(jobId)
        self.failUnlessEqual(trvMap, expected)
        mockHelper.getJob._mock.assertCalled(jobId)
        mockHelper.client.startCommit._mock.assertCalled(jobId)
        mockHelper.client.commitSucceeded._mock.assertCalled(sampleData)

        mockCommitJobs._mock.setDefaultReturn((False, sampleData))
        self.failUnlessRaises(errors.CommitFailedError, builder._commitJob, jobId)
        mockHelper.getJob._mock.assertCalled(jobId)
        mockHelper.client.startCommit._mock.assertCalled(jobId)
        mockHelper.client.commitFailed._mock.assertCalled([jobId, ], sampleData)
        mockHelper.client.commitSucceeded._mock.assertNotCalled()


testsetup.main()
