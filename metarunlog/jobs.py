#!/usr/bin/env python
# Metarunlog, experiment management tool.
# Author: Tom Sercu
# Date: 2015-03-12

import subprocess
import sys
from jinja2 import Template, Environment

# TODO
# structure Job similar to Popen object? -> needs startLocal() to return after launch, isAlive and terminate
# Then the scheduler could be starting jobs in turn, avoids race conditions in 
# but this complicates the multiple-command thing: need different start & terminate() s
# For now: assume the jobs dont interfere with each other and we can just launch them at the same time no problem.

# TODO self.resource = local / pbs / ssh
# Then kill job in object destructor
class Job:
    def __init__(self, jobName, jobTemplate, cmdParams, expId, absloc, jobId):
        self.jobName    = jobName
        self.jobTemplate= jobTemplate
        self.commandlist= [] # rendered jobTemplate
        self.cmdParams  = cmdParams
        self.expId      = expId
        self.absloc     = absloc
        self.jobId      = jobId #relloc
        # to be set later
        self.resourceType = None
        self.proc       = None
        self.outfh      = None
        # Three status flags:
        self.started    = False
        self.failed     = False
        self.finished   = False

    def renderCommands(self):
        """ Render the commands to run them in the shell.
        JIT rendering allows the scheduler to set parameters after the job has been initialized."""
        # always start out in mrl basedir
        self.commandlist = ['cd {}'.format(self.cmdParams['mrlBasedir'])] 
        for cmdTemplate in self.jobTemplate:
            self.commmandlist.append(cmdTemplate.render(self.cmdParams))

    def startLocal(self, outfh):
        self.started = True
        self.outfh = outfh
        outfh.write("Start job {} for expId {} at jobId {}\n".format(self.jobName, self.expId, self.jobId))
        self.renderCommands()
        shellcmd = '\n'.join(self.commandlist)
        outfh.write('Full shell command:\n{}\n=============\n'.format(shellcmd))
        try:
            self.proc = subprocess.Popen(shellcmd, stdout=outfh, shell=True)
        except OSError as e:
            outfh.write("Exception in subprocess {} {} : {}\n".format(self.jobName, self.expId, self.jobId))
            outfh.write(e.child_traceback)
            self.failed = 'OSError' 
            self.finished = True
            return
        self.resourceType = 'local'

    def updateStatus(self):
        if self.failed or self.finished:
            return 
        if self.started:
            if self.resourceType == 'local':
                self.finished = self.proc.poll() is None
                if self.finished:
                    self.failed = self.proc.poll() # 0 or exit code 
            elif self.resourceType == 'ssh':
                return False #TODO
            elif self.resourceType == 'pbs':
                return False #TODO

    def terminate(self):
        if self.started and not self.finished:
            if self.resourceType == 'local':
                self.proc.terminate()
            else:
                raise Exception("todo")

    def __del__(self):
        if self.started:
            if self.resourceType == 'local':
                print "Kill local job {}".format(self.jobId)
                # TODO use if needed: http://stackoverflow.com/questions/4789837/how-to-terminate-a-python-subprocess-launched-with-shell-true
                self.proc.kill()

    def startSsh(self, host, device):
        """ 
        ssh submit this job. Use some way of ssh polling to see if job is still alive and redirect its output?
        """
        raise Exception("todo")

    def startPbs(self, host, qsubparams):
        """ 
        qsub to hpc. but also poll if job is done etc. See spearmint for inspiration.
        also todo: deal with copying files over
        """
        raise Exception("todo")
