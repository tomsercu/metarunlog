#!/usr/bin/env python
# Metarunlog, experiment management tool.
# Author: Tom Sercu
# Date: 2015-03-12

from metarunlog import cfg #TODO are updates from __init__ also visible here? guess yes
from metarunlog.exceptions import *
from metarunlog.util import nowstring
import os
from os.path import isdir, isfile, join, relpath, expanduser
import sys
import time

class AbstractScheduler:
    def __init__(self, expDir, jobList, resourceName, resourceProp):
        self.expDir  = expDir
        self.jobList = jobList
        self.nextJobIx = 0
        self.resourceName = resourceName
        self.resourceProp = resourceProp
        self.sleepInterval = 5
        # Check if jobs already running
        # TODO make this a checkpoint for resuming an interrupted scheduler session, given a policy on resuming
        # interrupted job (for example: jobs dict defines "run": [...] and runResume: [...])
        if isfile(join(self.expDir, '.mrl.running')):
            raise SchedulerException("Lockfile exists: {}. Clear up situation first and remove lockfile."\
                    .format(join(self.expDir, '.mrl.running')))
        else:
            open(join(self.expDir, '.mrl.running'),"w").close()

    def main(self):
        while not all(job.isFinished() for job in self.jobList):
            resourceAvail = self.nextAvailableResource()
            if resourceAvail and not all(job.isStarted() for job in self.jobList):
                nextJob = self.jobList[self.nextJobIx]
                print('Start job {} {} on resource {}'.format(nextJob.jobName, nextJob.jobId, resourceAvail))
                self.startJob(nextJob, resourceAvail)
                self.nextJobIx += 1
            else:
                self.printStatus()
                self.sleep()
        self.printStatus()
        print('\nScheduler finished execution.')

    def nextAvailableResource(self):
        raise Exception("override")

    def startJob(self, resource):
        raise Exception("override")

    def sleep(self):
        time.sleep(self.sleepInterval)

    def printStatus(self):
        for job in self.jobList:
            msg = "{} {} ({}): ".format(job.jobName, job.jobId, self.resourceName)
            if job.started:
                if job.failed:
                    msg += 'FAILED: ' + str(job.failed)
                elif job.finished:
                    msg += 'FINISHED'
                else:
                    msg += 'RUNNING'
            else:
                msg += 'NOT STARTED'
            print(msg)
        print('---')

    def terminate(self):
        print("{} Sending SIGTERM to jobs", type(self).__name__)
        for job in self.jobList:
            job.terminate()

    def __del__(self):
        # kill all jobs before removing lockfile 
        ##TODO check that this actually kills children, see http://stackoverflow.com/questions/4789837/how-to-terminate-a-python-subprocess-launched-with-shell-true
        print("{} Sending SIGKILL to remaining jobs", type(self).__name__)
        del self.jobList[:]
        print("{} remove .mrl.running", type(self).__name__)
        os.remove(join(self.expDir, '.mrl.running'))

class localScheduler(AbstractScheduler):
    def __init__(self, expDir, jobList, resourceName, resourceProp):
        """ localScheduler has only one resource, 
        TODO: support multiple devices OR do not set the lockfile in runJobs
        """
        AbstractScheduler.__init__(self, expDir, jobList, resourceName, resourceProp)
        self.runningJob = None

    def nextAvailableResource(self):
        if not self.runningJob or not self.runningJob.isRunning():
            self.runningJob = None
            return 'local'
        else:
            return ''
        #TODO have multiple devices in config file

    def startJob(self, job, resource):
        assert not self.runningJob, "self.runningJob not None"
        job.startLocal()
        self.runningJob = job

class sshScheduler:
    def __init__(self):
        pass

class pbsScheduler:
    def __init__(self):
        pass
