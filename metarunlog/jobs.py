#!/usr/bin/env python
# Metarunlog, experiment management tool.
# Author: Tom Sercu
# Date: 2015-03-12

from metarunlog.exceptions import *
from metarunlog.util import nowstring
import subprocess
import sys
import os
import signal
from os.path import isdir, isfile, join, relpath, expanduser
from jinja2 import Template, Environment
import datetime

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
        self.jobId      = jobId # relloc will be used but doesn't have to
        # to be set later
        self.resourceType = None
        self.resourceName = ''
        self.proc       = None
        self.outfh      = None
        self.sshHost    = None
        self.sshPass    = None
        self.qsub       = None
        self.shellcmd   = None
        # Three status flags and statusUpdateTime:
        self.started    = False
        self.failed     = False
        self.finished   = False
        self.statusUpdateTime = datetime.datetime(1990,1,1)
        self.statusUpdateInterval = datetime.timedelta(milliseconds=300)

    def renderCmd(self, v=True):
        """ 
        Render the commands to run them in the shell.
        JIT rendering allows the scheduler to set parameters after the job has been initialized.
        renderCmd also takes self.sshHost, self.sshPass and self.qsub into account.
        """
        # always start out in mrl basedir
        self.commandlist = ['cd {}'.format(self.cmdParams['mrlBasedir'])] 
        for cmdTemplate in self.jobTemplate:
            self.commandlist.append(cmdTemplate.render(self.cmdParams))
        self.shellcmd = ' && '.join(self.commandlist)
        # sshHost and sshPass
        cleancmd = ''
        if self.sshHost:
            self.shellcmd = 'ssh {} "{}"'.format(self.sshHost, self.shellcmd)
            if self.sshPass:
                cleancmd = "sshpass -p '{}' {}".format('***', self.shellcmd)
                self.shellcmd = "sshpass -p '{}' {}".format(self.sshPass, self.shellcmd)
        # printing
        if not cleancmd: cleancmd = self.shellcmd
        if v: self.outfh.write('Full shell command:\n{}\n=============\n'.format(cleancmd))

    def startProc(self):
        try:
            self.proc = subprocess.Popen(self.shellcmd,
                                         stdout=self.outfh,
                                         stderr=subprocess.STDOUT,
                                         shell=True,
                                         preexec_fn=os.setsid)
        except OSError as e:
            self.outfh.write("Exception in subprocess launch of {}\n".format(str(self)))
            self.outfh.write(e.child_traceback)
            self.failed = 'OSError' 
            self.finished = True
            return

    def startLocal(self):
        self.started = True
        self.outfn = join(self.absloc, '{}_local_{}.log').format(self.jobName, nowstring(sec=False))
        self.outfh = open(self.outfn, 'w')
        self.outfh.write("Start job {}\n".format(str(self)))
        self.renderCmd()
        self.outfh.flush() # get this out before subproc writes into it
        self.startProc()
        self.resourceType = 'local'
        self.resourceName = 'local'
        self.updateStatus()

    def finishLocal(self):
        self.failed = self.proc.poll() # 0 or exit code 
        self.outfh.close()

    def startSsh(self, host, device, sshPass, copyFiles):
        """
        ssh submit this job. Just use subprocess, shell=True and launch ssh with the rendered command.
        Killing the subprocess kills the ssh session.
        """
        self.started = True
        self.outfn = join(self.absloc, '{}_ssh_{}_{}_{}.log').format(self.jobName, host, device, nowstring(sec=False))
        self.outfh = open(self.outfn, 'w')
        self.outfh.write("Start job {}\n".format(str(self)))
        self.cmdParams['device'] = device
        self.sshHost = host
        self.sshPass = sshPass
        self.renderCmd()
        self.outfh.flush() # get this out before subproc writes into it
        self.startProc()
        self.resourceType = 'ssh'
        self.resourceName = '{}[{}]'.format(host,device)
        self.updateStatus()

    def finishSsh(self, host, device):
        self.failed = self.proc.poll() # 0 or exit code 
        self.outfh.close()

    def startPbs(self, host, qsubparams):
        """ 
        qsub to hpc. but also poll if job is done etc. See spearmint for inspiration.
        also todo: deal with copying files over
        """
        raise Exception("todo")

    def updateStatus(self):
        if (not self.started) or self.finished:
            return # status wont change
        if datetime.datetime.now() - self.statusUpdateTime < self.statusUpdateInterval:
            return
        if self.started:
            if self.resourceType == 'local' or self.resourceType == 'ssh':
                self.finished = (self.proc.poll() is not None)
                if self.finished:
                    self.finishLocal()
            elif self.resourceType == 'pbs':
                return False #TODO
            else:
                raise SchedulerException("Dont know that resource type: {}".format(self.resourceType))
        self.statusUpdateTime = datetime.datetime.now()

    def isStarted(self):
        self.updateStatus()
        return self.started

    def isFinished(self):
        self.updateStatus()
        return self.finished

    def isFailed(self):
        self.updateStatus()
        return self.failed

    def isRunning(self):
        self.updateStatus()
        return self.started and not self.finished

    def terminate(self):
        if self.started and not self.finished:
            if self.resourceType == 'local' or self.resourceType == 'ssh':
                print "{} job {} - send SIGINT to proc group {}".\
                        format(self.resourceName, self.jobId, self.proc.pid)
                os.killpg(self.proc.pid, signal.SIGINT)
                #TODO why doesn sigint work here for torch, but it does work on a terminal? ssh -t flag?
                #os.killpg(self.proc.pid, signal.SIGTERM) # torch handles sigint better than sigterm.
            else:
                raise Exception("todo")

    def __del__(self):
        if self.isRunning():
            if self.resourceType == 'local' or self.resourceType == 'ssh':
                print "{} job {} - send SIGKILL to proc group {}".\
                        format(self.resourceName, self.jobId, self.proc.pid)
                os.killpg(self.proc.pid, signal.SIGKILL)
                # TODO sigkill on the ssh session doesnt sigkill the remote process. Open up a new ssh connection to sigkill? thats a mess
    def __str__(self):
        return "{} {} ({}): ".\
                format(self.jobName, self.jobId, self.resourceName if self.resourceName else 'unscheduled')
