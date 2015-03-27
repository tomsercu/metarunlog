#!/usr/bin/env python
# Metarunlog, experiment management tool.
# Author: Tom Sercu
# Date: 2015-03-12

from metarunlog.exceptions import *
from metarunlog.util import nowstring, sshify
import subprocess
import sys
import os
import signal
import re
from os.path import isdir, isfile, join, relpath, expanduser
from jinja2 import Template, Environment
import datetime

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
        self.qsubHeader = None
        self.shellcmd   = None
        # Three status flags and statusUpdateTime:
        self.started    = False
        self.failed     = False
        self.finished   = False
        self.statusUpdateTime = datetime.datetime(1990,1,1)
        self.statusUpdateInterval = datetime.timedelta(milliseconds=300)

    def renderCmd(self, v=True):
        """ 
        Render the commands in commandlist to shellcmd, to run them in the shell or over ssh.
        JIT rendering allows the scheduler to set parameters after the job has been initialized.
        renderCmd also takes self.sshHost, self.sshPass into account.
        """
        # always start out in mrl basedir
        self.commandlist = ['cd {}'.format(self.cmdParams['mrlBasedir'])] 
        for cmdTemplate in self.jobTemplate:
            self.commandlist.append(cmdTemplate.render(self.cmdParams))
        self.shellcmd = ' && '.join(self.commandlist)
        # sshHost and sshPass
        self.shellcmd = sshify(self.shellcmd, self.sshHost, self.sshPass, self.outfh)

    def cmdToScript(self, fn):
        """ 
        Render the commands in commandlist to a qsub script inside self.absloc and set up shellcmd to qsub it.
        """
        # write the script
        with open(join(self.absloc, fn),'w') as fh:
            for line in self.qsubHeader:
                fh.write(line + "\n")
            # always start out in mrl basedir
            fh.write('\ncd {}\n'.format(self.cmdParams['mrlBasedir']))
            for cmdTemplate in self.jobTemplate:
                fh.write(cmdTemplate.render(self.cmdParams) + '\n')
        os.chmod(join(self.absloc, fn), 0770)

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

    def finishProc(self):
        self.failed = self.proc.poll() # 0 or exit code 
        self.outfh.close()

    def copyFilesToRemote(self, v=True):
        """
        Scp files in self.absloc to self.sshHost with self.sshPass.
        This assumes exactly mirrored remote directory structure. Everything assumes this.
        """
        cmd = sshify("mkdir -p " + self.absloc, self.sshHost, self.sshPass, sys.stdout)
        subprocess.check_output(cmd, shell=True) # raises CalledProcessError
        cmd = "rsync -au {}/ {}:{}/".format(self.absloc, self.sshHost, self.absloc)
        cmd = sshify(cmd, None, self.sshPass, sys.stdout)
        subprocess.check_output(cmd, shell=True) # raises CalledProcessError

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
        self.resourceType = 'ssh'
        self.resourceName = '{}[{}]'.format(host,device)
        self.renderCmd()
        self.outfh.flush() # get this out before subproc writes into it
        # copy files
        try:
            if copyFiles: 
                self.copyFilesToRemote()
        except subprocess.CalledProcessError as e:
            print "Failed to copy the files to {}, job failed.".format(self.sshHost)
            self.finished = True
            self.failed = e.returncode
        else:
            self.startProc()
            self.updateStatus()

    def startPbs(self, host, sshPass, copyFiles, qsubHeader):
        """ 
        qsub to hpc and quit. In the future: keep polling with ssh qstat and parse output.
        """
        self.started = True
        self.sshHost = host
        self.sshPass = sshPass
        self.qsubHeader =qsubHeader
        self.cmdParams['device'] = 1
        self.resourceType = 'pbs'
        self.resourceName = '{}[{}]'.format(host, "failed")
        self.scriptfn = '{}_pbs_{}.q'.format(self.jobName, re.sub('[\W_]+', '_', self.jobId))
        self.cmdToScript(self.scriptfn)
        # copy files
        try:
            if copyFiles:
                self.copyFilesToRemote()
        except subprocess.CalledProcessError as e:
            print "Failed to copy the files to {}, job failed.".format(self.sshHost)
            self.finished = True
            self.failed = e.returncode
        else:
            #start proc and wait for its output
            self.shellcmd = 'cd {} && qsub {}'.format(self.absloc, self.scriptfn)
            self.shellcmd = sshify(self.shellcmd, self.sshHost, self.sshPass, sys.stdout)
            self.outfh = subprocess.PIPE
            self.startProc()
            stdout, stderr_empty = self.proc.communicate()
            self.finished = True
            self.failed = self.proc.poll() # return code
            if self.failed:
                print "qsubbing failed: {}".format(stdout)
            else:
                qsubid = stdout.replace('\n','')
                self.resourceName = '{}[{}]'.format(host, qsubid)

    def updateStatus(self):
        if (not self.started) or self.finished:
            return # status wont change
        if datetime.datetime.now() - self.statusUpdateTime < self.statusUpdateInterval:
            return
        # regular update
        if self.resourceType == 'local' or self.resourceType == 'ssh':
            self.finished = (self.proc.poll() is not None)
            if self.finished:
                self.finishProc()
        elif self.resourceType == 'pbs':
            raise SchedulerException("Pbs should never be updated as it finishes right away")
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
