#!/usr/bin/env python
# Metarunlog, experiment management tool.
# Author: Tom Sercu
# Date: 2015-03-12

import os
from os.path import isdir, isfile, join, relpath, expanduser
import time

class AbstractScheduler:
    def __init__(self, expDir, jobList, resourceName, resourceProp):
        self.expDir = expDir
        self.jobList= jobList
        self.resourceName = resourceName
        self.resourceProp = resourceProp
        self.sleepInterval = 5
        # Check if jobs already running
        if isfile(join(self.expDir, '.mrl.running')):
            raise SchedulerException("Lockfile exists: {}. Clear up situation first and remove lockfile."\
                    .format(join(self.expDir, '.mrl.running')))
        else:
            open(join(self.expDir, '.mrl.running'),"w").close()

    def main(self):
        while not all(job.finished for job in self.jobList):
            resourceAvail = self.nextAvailableResource()
            if not all(self.started for job in self.jobList) and resourceAvail:
                self.startNextJob(resourceAvail)
            else:
                self.printStatus()
                self.sleep()
            [job.updateStatus() for job in self.jobList]
        self.printStatus()

    def nextAvailableResource(self):
        raise Exception("override")

    def startNextJob(self, resource):
        raise Exception("override")

    def sleep(self):
        time.sleep(self.sleepInterval)

    def printStatus(self):
        for job in self.jobList:
            msg = "{} on {} - expId {} jobId {}: ".format(job.jobName, self.resourceName, job.expId, job.jobId)
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

    def terminate():
        for job in self.jobList:
            job.terminate()

    def __del__(self):
        # kill all jobs before removing lockfile #TODO check that this actually does what its supposed to
        del self.jobList[:]
        os.remove(join(self.expDir, '.mrl.running'))

class localScheduler(AbstractScheduler):
    def __init__(self, **args):
        """ localScheduler has only one resource, TODO: support multiple devices OR dont set the lockfile
        """
        AbstractScheduler.__init__(self)
        self.runningProcess = None

    def nextAvailableResource(self):
        if self.runningProcess.terminated:
            self.runningProcess

class sshScheduler:
    def __init__(self):
        pass

class pbsScheduler:
    def __init__(self):
        pass
