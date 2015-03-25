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
            if resourceAvail is not None and not all(job.isStarted() for job in self.jobList):
                nextJob = self.jobList[self.nextJobIx]
                print('Start job {} on resource {}'.format(str(nextJob), self.fmtResource(resourceAvail)))
                self.startJob(nextJob, resourceAvail)
                self.nextJobIx += 1
            else:
                self.printStatus()
                self.sleep()
        self.printStatus()
        print('\nScheduler finished execution.')

    def nextAvailableResource(self):
        """ 
        returns the next available resource in a format understood by startJob,
        or the None object if no resource available.
        """
        raise Exception("override")

    def startJob(self, resource):
        raise Exception("override")

    def fmtResource(self, resource):
        raise Exception("override")

    def sleep(self):
        time.sleep(self.sleepInterval)

    def printStatus(self):
        for job in self.jobList:
            msg = str(job)
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
        """ 
        returns 'local' if it is available, 
        or the None object if a job is running.
        """
        if not self.runningJob or not self.runningJob.isRunning():
            self.runningJob = None
            return 'local'
        else:
            return None
        #TODO have multiple devices in config file

    def startJob(self, job, resource):
        assert not self.runningJob, "self.runningJob not None"
        job.startLocal()
        self.runningJob = job

    def fmtResource(self, resource):
        return resource

class sshScheduler:
    def __init__(self, expDir, jobList, resourceName, resourceProp):
        AbstractScheduler.__init__(self, expDir, jobList, resourceName, resourceProp)
        self.hosts = [(host, int(dev)) for host,dev in self.resourceProp.hosts]
        self.runningJobs = [None for slot in self.hosts]

    def nextAvailableResource(self):
        """
        returns index into self.hosts if a host is available,
        or the None object if all hosts are running a job.
        """
        try:
            return self.runningJobs.index(None)
        except ValueError:
            return None

    def startJob(self, job, resource):
        assert self.runningJobs[resource] is None, "Host {} has job {} running".\
                format(self.fmtResource(resource), str(self.runningJobs[resource]))
        host, device = self.hosts[resource]
        copyFiles = self.resourceProp['copyFiles']
        job.startSsh(host, device, copyFiles)
        self.runningJobs[resource] = job

    def fmtResource(self, resource):
        return '{} [device {}]'.format(*self.hosts[resource])

class pbsScheduler:
    def __init__(self):
        pass
