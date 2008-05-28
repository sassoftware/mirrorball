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
Builder object implementation.
'''

import time
import logging

from rmake.cmdline import helper, monitor, commit

from updatebot.errors import JobFailedError, CommitFailedError

log = logging.getLogger('updateBot.build')

class Builder(object):
    '''
    Class for wrapping the rMake api until we can switch to using rBuild.

    @param cfg: updateBot configuration object
    @type cfg: config.UpdateBotConfig
    '''

    # R0903 - Too few public methods
    # pylint: disable-msg=R0903

    def __init__(self, cfg):
        self._cfg = cfg

        self._helper = helper.rMakeHelper(root=self._cfg.configPath)


    def build(self, troveSpecs):
        '''
        Build a list of troves.
        @param troveSpecs: list of trove specs
        @type troveSpecs: [(name, versionObj, flavorObj), ...]
        @return troveMap: dictionary of troveSpecs to built troves
        '''

        # Create rMake job
        log.info('Creating build job: %s' % (troveSpecs, ))
        job = self._helper.createBuildJob(troveSpecs)
        jobId = self._helper.buildJob(job)
        log.info('Started jobId: %s' % jobId)

        # Watch build, wait for completion
        monitor.monitorJob(self._helper.client, jobId,
            exitOnFinish=True, displayClass=_StatusOnlyDisplay)

        # Check for errors
        job = self._helper.getJob(jobId)
        if job.isFailed():
            log.error('Job %d failed', jobId)
            raise JobFailedError(jobId=jobId, why='Job failed')
        elif not job.isFinished():
            log.error('Job %d is not done, yet watch returned early!', jobId)
            raise JobFailedError(jobId=jobId, why='Job not done')
        elif not list(job.iterBuiltTroves()):
            log.error('Job %d has no built troves', jobId)
            raise JobFailedError(jobId=jobId, why='Job built no troves')

        # Do the commit
        startTime = time.time()
        log.info('Starting commit of job %d', jobId)
        self._helper.client.startCommit(jobId)
        succeeded, data = commit.commitJobs(self._helper.getConaryClient(),
                                            [job, ],
                                            self._helper.buildConfig.reposName,
                                            self._cfg.commitMessage)
        if not succeeded:
            self._helper.client.commitFailed([jobId, ], data)
            raise CommitFailedError(jobId=job.jobId, why=data)

        log.info('Commit of job %d completed in %.02f seconds',
                 jobId, time.time() - startTime)

        troveMap = {}
        for _, troveTupleDict in data.iteritems():
            for buildTroveTuple, committedList in troveTupleDict.iteritems():
                troveMap[buildTroveTuple] = committedList

        self._helper.client.commitSucceeded(data)

        return troveMap


class _StatusOnlyDisplay(monitor.JobLogDisplay):
    '''
    Display only job and trove status. No log output.

    Copied from bob3
    '''

    # R0901 - Too many ancestors
    # pylint: disable-msg=R0901

    def _troveLogUpdated(self, (jobId, troveTuple), state, status):
        '''Don't care about trove logs'''
        pass

    def _trovePreparingChroot(self, (jobId, troveTuple), host, path):
        '''Don't care about resolving/installing chroot'''
        pass
