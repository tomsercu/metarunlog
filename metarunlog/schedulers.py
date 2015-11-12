#!/usr/bin/env python
# Metarunlog, experiment management tool.
# Author: Tom Sercu
# Date: 2015-03-12

from metarunlog.exceptions import *
from metarunlog.util import nowstring
import os
from os.path import isdir, isfile, join, relpath, expanduser
import sys
import time
import getpass

class AbstractScheduler:
    def __init__(self, expDir, jobList, resourceName, resourceProp):
        self.expDir  = expDir
        self.jobList = []
        self.runningJobs = None # override
        for job in jobList: self.addNewJob(job)
        self.resourceName = resourceName
        self.resourceProp = resourceProp
        self.sleepInterval = resourceProp.get('sleepInterval', 5)
        self.sshPass = getpass.getpass("Password for {}: ".format(self.resourceName))\
                if resourceProp.get('askPass', False) else None
        self.copyFiles = self.resourceProp.get('copyFiles', False)
        # Check if jobs already running
        # TODO make this a checkpoint for resuming an interrupted scheduler session, given a policy on resuming
        # interrupted job (for example: jobs dict defines "run": [...] and runResume: [...])
        #if isfile(join(self.expDir, '.mrl.running')):
            #raise SchedulerException("Lockfile exists: {}. Clear up situation first and remove lockfile."\
                    #.format(join(self.expDir, '.mrl.running')))
        #else:
            #open(join(self.expDir, '.mrl.running'),"w").close()

    def main(self):
        while not all(job.isFinished() for job in self.jobList):
            finishedJobs = self.popFinishedJobs()
            nextResource = self.nextAvailableResource()
            nextJob      = self.nextJob()
            if nextResource is not None and nextJob:
                print('Start job {} on resource {}'.format(str(nextJob), self.fmtResource(nextResource)))
                self.startJob(nextJob, nextResource)
            else:
                self.printStatus()
                self.sleep()
        self.printStatus()
        print('\nScheduler finished execution.')

    def addNewJob(self, job):
        self.jobList.append(job)

    def nextJob(self):
        """ Get next job: first the jobs that have to be resumed, then jobs that haven't started yet. """
        for job in self.jobList:
            if job.started and not job.finished and not job in self.runningJobs:
                return job #to be resumed
        for job in self.jobList:
            if not job.started:
                return job
        return None

    def popFinishedJobs(self):
        finished         = [job for job in self.runningJobs if (job and not job.isRunning())]
        self.runningJobs = [job if (job and job.isRunning()) else None for job in self.runningJobs]
        return finished

    def nextAvailableResource(self):
        """
        returns index of first available slot if a slot is available,
        or the None object if all resource slots are running a job.
        """
        try:
            return self.runningJobs.index(None)
        except ValueError:
            return None

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
                    if job in self.runningJobs:
                        msg += 'RUNNING'
                    else:
                        msg += 'TO BE RESUMED'
            else:
                msg += 'NOT STARTED'
            print(msg)
        print('---')

    def terminate(self):
        rjobs = [job for job in self.runningJobs if job is not None]
        if rjobs:
            print("{} Asking running jobs to terminate.".format(self.__class__.__name__))
            for job in rjobs:
                job.terminate()

    def __del__(self):
        # kill all jobs before removing lockfile 
        rjobs = [job for job in self.runningJobs if job is not None]
        if rjobs:
            print("{} Sending SIGKILL to remaining jobs".format(self.__class__.__name__))
        del self.jobList[:]
        #print("{} remove .mrl.running".format(self.__class__.__name__))
        #os.remove(join(self.expDir, '.mrl.running'))

class localScheduler(AbstractScheduler):
    def __init__(self, expDir, jobList, resourceName, resourceProp):
        """ localScheduler has only one resource, 
        TODO: support multiple devices OR do not set the lockfile in runJobs
        """
        AbstractScheduler.__init__(self, expDir, jobList, resourceName, resourceProp)
        self.runningJobs = [None] # one slot

    def startJob(self, job, slotIx):
        assert self.runningJobs[slotIx] is None, "Host {} has job {} running".\
                format(self.fmtResource(slotIx), str(self.runningJobs[slotIx]))
        job.startLocal()
        self.runningJobs[slotIx] = job

    def fmtResource(self, resource):
        return 'local'

class sshScheduler(AbstractScheduler):
    def __init__(self, expDir, jobList, resourceName, resourceProp):
        AbstractScheduler.__init__(self, expDir, jobList, resourceName, resourceProp)
        self.hosts = [(host, int(dev)) for host,dev in self.resourceProp['hosts']]
        self.runningJobs = [None for slot in self.hosts]

    def startJob(self, job, slotIx):
        assert self.runningJobs[slotIx] is None, "Host {} has job {} running".\
                format(self.fmtResource(slotIx), str(self.runningJobs[slotIx]))
        host, device = self.hosts[slotIx]
        job.startSsh(host, device, self.sshPass, self.copyFiles)
        self.runningJobs[slotIx] = job

    def fmtResource(self, slotIx):
        return '{} [device {}]'.format(*self.hosts[slotIx])

class pbsScheduler(AbstractScheduler):
    """ Note, pbsScheduler and job.startPbs() is not implemented for monitoring yet.
    It just qsubs all the jobs, waits for the qsub proc to finish,
    and finishes without sending any sigint or sigkills.
    """
    def __init__(self, expDir, jobList, resourceName, resourceProp):
        AbstractScheduler.__init__(self, expDir, jobList, resourceName, resourceProp)
        self.host = self.resourceProp['host']
        self.runningJobs = [None] # only one slot since it finishes right away

    def startJob(self, job, slotIx):
        assert self.runningJobs[slotIx] is None, "Pbs scheduler should not have a job running (should finish right away)"
        job.startPbs(self.host, self.sshPass, self.copyFiles, self.resourceProp.get('qsubHeader', []))
        self.runningJobs[slotIx] = job

    def fmtResource(self, resource):
        return resource
    def terminate(self):
        pass
    def __del__(self):
        #print("{} remove .mrl.running".format(self.__class__.__name__))
        #os.remove(join(self.expDir, '.mrl.running'))
        pass
