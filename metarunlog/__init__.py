#!/usr/bin/env python
# Metarunlog, experiment management tool.
# Author: Tom Sercu
# Date: 2015-01-23

from  metarunlog import cfg # NOTE cfg is modified by MetaRunLog._loadBasedirConfig() with custom configuration.
from metarunlog.exceptions import *
from metarunlog.util import nowstring, sshify, _decode_dict, _decode_list
import os
import sys
from os import listdir
from os.path import isdir, isfile, join, relpath, expanduser
import argparse
import subprocess
try:
    import simplejson as json # way better error messaging
except:
    import json
import pdb
import datetime
from collections import OrderedDict
from shutil import copy as shcopy
import shutil
from jinja2 import Template, Environment, meta
import itertools
import getpass
from jobs import Job

DEBUG = True

def get_commit():
    cline = subprocess.check_output("git log -n1 --oneline", shell=True)
    #print "cline: ", cline
    cline = cline.split()
    return (cline[0], " ".join(cline[1:]))

def initBasedir(basedir, args):
    """ init basedir"""
    # check if it already is a valid basedir, then raise an exception
    try:
        mrlState = MetaRunLog(basedir)
    except NoBasedirConfig:
        pass # should be raised
    else:
        return "{} already has valid .mrl.cfg file, remove it first to re-init.".format(basedir)
    # initialize .mrl.cfg file as a json-dict copy of cfg.py template
    with open(join(basedir, '.mrl.cfg'),"w") as fh:
        # copy the cfg attributes into ordered dict
        bconf = {k:getattr(cfg,k) for k in dir(cfg) if '__' not in k}
        bconf['outdir'] = args.outdir
        json.dump(bconf, fh, indent=2)
        fh.write("\n")
    try:
        mrlState = MetaRunLog(basedir)
    except Exception as e:
        print("initBasedir() - Failed to init basedirconfig")
        raise
    else:
        return join(basedir, ".mrl.cfg")

class ConfParser:
    """
    ConfParser class is initialized with batch-template (list of lines)
    including the last lines determining the values,
    and generates self.output as a list of strings (that can be written to file).
    """
    def __init__(self, templatefile):
        try:
            with open(templatefile) as fh:
                self.template = fh.readlines()
        except jinja2.exceptions.TemplateSyntaxError as e:
            err = "TemplateSyntaxError in your {} template file: \n {}".format(cfg.confTemplFile, str(e))
            raise ConfParserException(err)
        self.jtmpl = Template("".join(self.template))
        grid = OrderedDict()
        params = [{}]
        whetlab= {}
        # iterate over last lines and parse them to collect grid parameters.
        # correct formatting of mrl instructions:
        # [something] MRL:grid['key'] = [vallist]
        # where [something] is comment symbol. The space after it is essential.
        for line in self.template[::-1]:
            if not line.strip(): continue
            line = line.split(None, 1)[-1].split(":",1) #discard comment symbol
            if line[0] != 'MRL': break
            exec(line[1]) #add to grid / params / whetlab
        # construct output params list
        keys = grid.keys()
        vals = list(itertools.product(*[grid[k] for k in keys]))
        self.params = [dict(zip(keys, v)) for v in vals]
        self.params = [dict(d1.items() + d2.items()) for d1,d2 in itertools.product(self.params, params)]
        self.output = []
        for i, param in enumerate(self.params):
            self.output.append((i+1, param, self.renderFromParams(param)))
        # save the whetlab hyperparams
        self.whetlabHyperParameters = whetlab

    def renderFromParams(self, params):
        """ Render the configuration file template from given parameters. """
        return self.jtmpl.render(**params)

class MetaRunLog:
    """
    Metarunlog state from which all actions are coordinated.
    Needs to be run from a valid basedir (with .mrl.cfg file).
    Initialization overwrites cfg module from .mrl.cfg: metarunlog.cfg.py should be
    seen as a template for .mrl.cfg.
    """
    def __init__(self, basedir):
        self.basedir = basedir
        self._loadBasedirConfig()
        self.outdir  = join(self.basedir, cfg.outdir)
        if not isdir(self.outdir): raise InvalidOutDirException("Need output directory " + self.outdir + "  Fix your .mrl.cfg file")
        self.expDirList = sorted([x for x in listdir(self.outdir) if self._checkValidExp(x)])
        self.expList = [int(x) for x in self.expDirList]
        self.lastExpId = None if not self.expList else self.expList[-1]
        # parse the job commands into templates and extract the optional arguments for argparse
        self.jEnv = Environment()
        self.jobTemplates = {jobName:[]  for jobName in cfg.jobs.keys()}
        self.jobOptVars = {jobName:set() for jobName in cfg.jobs.keys()}
        for jobName, cList in cfg.jobs.iteritems():
            for cmd in cList:
                self.jobTemplates[jobName].append(self.jEnv.from_string(cmd))
                self.jobOptVars[jobName].update(meta.find_undeclared_variables(self.jEnv.parse(cmd)))

    def _loadBasedirConfig(self):
        try:
            with open(join(self.basedir, '.mrl.cfg')) as fh:
                bconf = json.load(fh, object_hook=_decode_dict)
                for k,v in bconf.iteritems():
                    setattr(cfg,k,v)
            return True
        except Exception as e:
            raise NoBasedirConfig(self.basedir, str(e))

    def new(self,args):
        expId = 1 if not self.lastExpId else self.lastExpId+1
        expConfig = OrderedDict()
        expConfig ['expId'] = expId
        expConfig['basedir'] = self.basedir
        gitclean = not bool(args.notclean)
        expConfig['gitFailUntracked']= args.gitFailUntracked
        untracked = 'no' if args.gitFailUntracked == 'no' else 'normal'
        uncommited = subprocess.check_output("git status --porcelain --untracked=" + untracked, shell=True)
        #print "uncommited: ", uncommited
        if gitclean and uncommited:
            raise NoCleanStateException("new: uncommited files -- please commit changes first\n" + uncommited)
        expConfig['gitHash'], expConfig['gitDescription'] = get_commit()
        if not gitclean and uncommited: expConfig['gitHash'] += '-sloppy'
        expConfig['timestamp'] = nowstring()
        expConfig['user'] = getpass.getuser()
        expConfig['description'] = args.description if args.description else ""
        # make dir and symlink
        expDir = self._getExpDir(expId, True)
        if self.lastExpId and os.path.lexists(join(self.basedir,'last')): 
            os.remove(join(self.basedir,'last'))
        os.symlink(relpath(expDir,self.basedir), join(self.basedir, 'last'))
        os.mkdir(expDir)
        # After this point: expDir is made, no more exception throwing! copy config files
        try:
            if args.copyConfigFrom == 'no':
                pass
            else:
                srcDir = self._getExpDir(self._resolveExpId(args.copyConfigFrom))
                self._copyConfigFrom(srcDir, expDir)
        except (InvalidExpIdException, IOError) as e:
            print("Can't copy config files. ")
            print(e)
            print("Still succesfully created new experiment directory.")
        self._saveExpDotmrl(expDir, expConfig)
        self._putEmptyNote(expDir, expConfig['description'])
        self.lastExpId = expId
        return expDir

    def info(self, args):
        """ load info from experiment id and print it """
        expId, expDir, expConfig = self._loadExp(args.expId)
        subExpList = self._getSubExperiments(expDir)
        items = ['',expDir,'']
        maxkeylen = max(len(k) for k,v in expConfig.iteritems())
        items += ["%*s : %.80s" % (maxkeylen,k,str(v)) for k,v in expConfig.iteritems()]
        items += ["%*s : %.80s" % (maxkeylen, 'subExperiments', str(subExpList))]
        return "\n".join(items)

    def ls(self, args):
        for expId in self.expList[::-1]:
            expConfig = self._getExpConf(expId)
            row = self._fmtSingleExp(expId)
            if args.tm:
                row += "\t" + expConfig['timestamp']
            if args.ghash:
                row += "\t" + expConfig['gitHash']
            if args.gdesc:
                row += "\t" + expConfig['gitDescription']
            if args.desc:
                row += "\t" + expConfig['description']
            print row
        return ""

    def makebatch(self, args):
        expId, expDir, expConfig = self._loadExp(args.expId)
        # check if already expanded in batch and cancel
        oldSubExpList = self._getSubExperiments(expDir)
        if oldSubExpList:
            if args.replace:
                # just remove all these subfolders. Drastic but it wouldn't make sense to keep results from old config files.
                print "Will remove all old subexperiments: {}".format(oldSubExpList)
                for subExp in oldSubExpList:
                    shutil.rmtree(join(expDir, subExp))
            else:
                raise BatchException("Experiment {} is already expanded into subexperiments: {}".\
                        format(expId, str(oldSubExpList)))
        # make ConfParser object
        confP = ConfParser(join(expDir, cfg.confTemplFile))
        # check if ConfParser output is non-empty
        if not confP.output:
            err = "ConfParser output is empty, are you sure {} is a batch template?"
            err = err.format(join(expDir, cfg.confTemplFile))
            raise BatchException(err)
        # generate output directories, write the output config files
        for i, params, fileContent in confP.output:
            self._newSubExp(expDir, i, {'params': params}, fileContent)
        # update the current .mrl file
        subExpList = self._getSubExperiments(expDir)
        return "Generated subExperiments {} for expId {}.\n".format(subExpList, expId)

    def hpcFetch(self, args):
        expId, expDir, expConfig = self._loadExp(args.expId)
        remoteExpDir = expDir
        hpcServer = cfg.resources['hpc']['host']
        if cfg.resources['hpc']['askPass']:
            hpcPass = getpass.getpass("Password for hpc: ")
        # Locations to fetch from
        runLocs = self._getRunLocations(expId, args.subExpId, expConfig, relativeTo=expDir)
        # Exclude datafiles ifneeded
        if not args.data:
            excludes = " ".join(['--exclude={}'.format(datafile) for datafile in cfg.hpcOutputData])
        else:
            excludes = ""
        for loc in runLocs:
            cmd = "rsync -aP {} {}:{}/ {}/".format(excludes, hpcServer, join(remoteExpDir,loc), join(expDir,loc))
            cmd = sshify(cmd, None, hpcPass, sys.stdout)
            try:
                out = subprocess.check_output(cmd, shell=True)
            except subprocess.CalledProcessError as e:
                # remove pwd from cmd
                raise HpcException('Couldnt fetch files from hpc')

    def _makeJobList(self, jobName, expId, args):
        expId, expDir, expConfig = self._loadExp(expId)
        jobTemplate = self.jobTemplates[jobName]
        if (not args.subExpId) or args.subExpId == 'all':
            jobList = []
            subExpIds = self._getSubExperiments(expDir)
            for subExpId in subExpIds:
                print "Make job '{}' for subExperiment {}".format(jobName, subExpId)
                relloc = join(self._fmtSingleExp(expId), subExpId)
                cmdParams = self._getCmdParams(expConfig, args, relloc)
                jobList.append(Job(jobName, jobTemplate, cmdParams.copy(), join(expDir, subExpId)))
        elif args.subExpId == 'single': # not expanded
            print "Make single job '{}' for expId {}".format(jobName, expId)
            relloc = self._fmtSingleExp(expId)
            cmdParams = self._getCmdParams(expConfig, args, relloc)
            jobList = [Job(jobName, jobTemplate, cmdParams.copy(), expDir)]
        else:
            # try to parse single subExpId from expanded
            try:
                subExpId = self._fmtSubExp(int(args.subExpId))
                print "Make job '{}' for subExperiment {}".format(jobName, subExpId)
                relloc = join(self._fmtSingleExp(expId), subExpId)
                cmdParams = self._getCmdParams(expConfig, args, relloc)
                jobList = [Job(jobName, jobTemplate, cmdParams.copy(), join(expDir, subExpId))]
            except ValueError as e:
                raise JobException("Invalid subExpId {} - {}".format(args.subExpId, str(e)))
        return jobList

    def runJobs(self, args):
        import schedulers
        expId, expDir, expConfig = self._loadExp(args.expId)
        # Make scheduler
        jobList = self._makeJobList(args.jobName, expId, args)
        resource = cfg.resources[args.resource]
        schedType = resource['scheduler']
        schedClass = getattr(schedulers, schedType+"Scheduler")
        sched = schedClass(expDir, jobList, args.resource, resource)
        # start scheduler
        try:
            sched.main()
        except KeyboardInterrupt as e:
            # catch keyboardinterrupt and kill all jobs
            print ("mrl caught KeyboardInterrupt, terminating running jobs")
            sched.terminate() # send SIGTERM
            sched.sleep()
            del sched # destructor sends SIGKILL to all jobs

    def whetlab(self, args):
        #TODO refactor this mess
        import whetlab
        from metarunlog import mrlWhetlab
        import schedulers
        # get the custom-for-this-job scoreFunction and scoreName
        jobName = cfg.whetlab['jobName']
        scoreName = getattr(mrlWhetlab, jobName + 'ScoreName')
        scoreFunc = getattr(mrlWhetlab, jobName + 'ScoreFunc')
        expId, expDir, expConfig = self._loadExp(args.expId)
        #assert 'batchlist' not in expConfig, "TODO continue whetlab run"
        # prepare the scheduler on the right resource and existing jobs
        jobList = self._makeJobList(jobName, expId, args)
        assert False, "TODO joblist wont be empty bc single-exp change"
        resource = cfg.resources[args.resource]
        schedType = resource['scheduler']
        schedClass = getattr(schedulers, schedType+"Scheduler")
        sched = schedClass(expDir, jobList, args.resource, resource)
        # load template and get hyperparameters
        confTemplate = ConfParser(join(expDir, cfg.confTemplFile))
        hyperparameters = confTemplate.whetlabHyperParameters
        for k,v in hyperparameters.iteritems():
            assert ('min' in v and 'max' in v and 'type' in v), "whetlab parameter dictionary needs min, max, type. In {} : {}".format(k,v)
        # make whetlab connection
        scientist = whetlab.Experiment(access_token=cfg.whetlab['token'],
                                       name='{}{}'.format(cfg.whetlab['expNamePrefix'], expId),
                                       description=expConfig['description'],
                                       parameters=hyperparameters,
                                       outcome={'name':scoreName})
        # main loop
        # TODO set keyboard interrupt to do final checkpoint
        while len(self._getSubExperiments(expDir)) < cfg.whetlab['maxExperiments'] or \
                not all(job.isFinished() for job in sched.jobList):
            # update whetlab with finished jobs
            finishedJobs  = sched.popFinishedJobs()
            for job in finishedJobs:
                try:
                    job.score = scoreFunc(job.absloc)
                    scientist.update(job.params, job.score)
                except:
                    scientist.update_as_failed(job.params)
            # if available resources, make and schedule next job
            nextResource = sched.nextAvailableResource()
            if nextResource is not None:
                nextJob = sched.nextJob()
                if not nextJob:
                    # get params from whetlab, make new subExperiment, make new job, schedule it.
                    params = scientist.suggest()
                    whetlabId = scientist.get_id(params)
                    subExpId = len(self._getSubExperiments(expDir)) + 1
                    confContent = confTemplate.renderFromParams(params)
                    self._newSubExp(expDir, subExpId, {'params':params, 'whetlabId':whetlabId}, confContent)
                    relloc = join(self._fmtSingleExp(expId), self._fmtSubExp(subExpId))
                    absloc = join(self.outdir, relloc)
                    cmdParams = self._getCmdParams(expConfig, args, relloc)
                    nextJob = Job(jobName, self.jobTemplates[jobName], cmdParams, absloc)
                    sched.addNewJob(nextJob)
                    nextJob = sched.nextJob()
                print('Start job {} on resource {}'.format(str(nextJob), sched.fmtResource(nextResource)))
                sched.startJob(nextJob, nextResource)
                sched.printStatus()
            else:
                sched.printStatus()
                sched.sleep()
        sched.printStatus()
        print('\nScheduler finished execution.')

    def _loadSubExp(self, subExpDir):
        with open(join(subExpDir, '.mrl')) as fh:
            return json.load(fh, object_hook=_decode_dict)

    def analyze(self, args):
        import pandas as pd
        import analyze
        expId, expDir, expConfig = self._loadExp(args.expId)
        print "Analyze expId {} in path {}".format(expId, expDir)
        outdir = args.outdir if args.outdir else join(expDir, 'analysis')
        if not os.path.exists(outdir): os.mkdir(outdir)
        # load the params into dataframe
        subExpIds = self._getSubExperiments(expDir)
        if subExpIds:
            try:
                paramList = [self._loadSubExp(join(expDir,subExpId))['params'] for subExpId in subExpIds]
            except IOError: # old style, with batchlist in expDir/.mrl
                paramList = expConfig['batchlist']
                subExpIds = [self._fmtSubExp(subExpId) for subExpId in range(1,len(paramList)+1)]
            Dparams = pd.DataFrame(paramList, index=subExpIds)
        outhtml = analyze.HtmlFile()
        title = 'Experiment {} - {}'.format(cfg.singleExpFormat.format(expId=expId), expConfig['timestamp'].split('T')[0])
        if 'description' in expConfig and expConfig['description']: title += ' - ' + expConfig['description']
        outhtml.addTitle(title)
        outhtml.parseNote(join(expDir,'.mrl.note'))
        # TODO keep analysis functions in order by using ordereddict in .mrl.cfg and cfg.py
        if subExpIds:
            # analysis_overview functions
            for funcname, xtrargs in cfg.analysis_overview.items():
                outhtml.addHeader('{} - {}'.format('overview', funcname), 1)
                retval = getattr(analyze, funcname)(expDir, outdir, subExpIds, Dparams, *xtrargs)
                outhtml.addRetVal(retval)
        # per exp functions
        if subExpIds:
            for subExpId in subExpIds:
                subExpDir = join(expDir, subExpId)
                outhtml.addHeader('{} - {}'.format('subExp', subExpId), 1)
                for funcname, xtrargs in cfg.analysis_subexp.items():
                    outhtml.addHeader('{}'.format(funcname), 2)
                    retval = getattr(analyze, funcname)(subExpDir, outdir, Dparams, subExpId, *xtrargs)
                    outhtml.addRetVal(retval)
        else:
            for funcname, xtrargs in cfg.analysis_subexp.items():
                outhtml.addHeader('{}'.format(funcname), 1)
                retval = getattr(analyze, funcname)(expDir, outdir, None, 'def', *xtrargs)
                outhtml.addRetVal(retval)
        outhtml.render(join(outdir, 'index.html'))
        if cfg.analysis_webdir:
            webdir = join(cfg.analysis_webdir, self._fmtSingleExp(expId))
            if not os.path.exists(webdir):
                os.mkdir(webdir)
            subprocess.call("cp -r {}/* {}/".format(outdir, webdir), shell=True)
            subprocess.call("chmod -R a+r {}".format(webdir), shell=True)
            subprocess.call(r"find %s -type d -exec chmod a+x {} \;"%(webdir), shell=True)
            print "Copied to webdir {}".format(webdir)

    def _getSubExperiments(self, expDir):
        """ returns a list of the existing subexperiments as formatted strings """
        subexp = []
        for subdir in listdir(expDir):
            try:
                if self._fmtSubExp(int(subdir)) == subdir:
                    subexp.append(str(subdir))
            except ValueError:
                pass
        return subexp

    def _getRunLocations(self, expId, subExpId, expConfig, relativeTo=''):
        expDir = self._getExpDir(expId)
        subExpList = self._getSubExperiments(expDir)
        if subExpList:
            if subExpId == 'all':
                locs = subExpList
            elif subExpId.isdigit():
                if self._fmtSubExp(int(subExpId)) not in subExpList:
                    raise SubExpIdException("subExpId {} out of range (batch size {} in expConfig)".format(subExpId,len(subExpList)))
                locs = [self._fmtSubExp(int(subExpId)), ]
            else:
                # TODO list of subexpids? can be handy
                raise SubExpIdException("Don't understand subExpId {}.".format(subExpId))
        else:
            locs = ['']
        if relativeTo != expDir:
            locs = [join(expDir, loc) for loc in locs]
            if relativeTo:
                locs = [relpath(loc, relativeTo) for loc in locs]
        return locs

    def _fmtSingleExp(self, expId):
        # TODO change fmtSingleExp to fetch date from a list initialized in init, then fill in that date here.
        return cfg.singleExpFormat.format(expId=expId)

    def _fmtSubExp(self, subExpId):
        return cfg.subExpFormat.format(subExpId=subExpId)

    def _relpathUser(self, path):
        return '~/' + relpath(path, expanduser('~'))

    def _copyConfigFrom(self, src, dst):
        for cfn in cfg.copyFiles:
            shcopy(join(src,cfn), join(dst, cfn))

    def _getCmdParams(self, expConfig, args, relloc):
        """
        Make the dictionary that is needed to render a job template into actual commands.
        note optional parameters override everything except relloc and absloc. And device, by startSsh or startPbs
        """
        cmdParams = {'mrlOutdir': self.outdir, 'mrlBasedir': self.basedir}
        cmdParams.update(expConfig)
        cmdParams.update({k:getattr(cfg, k) for k in dir(cfg) if '_' not in k}) # access to cfg params
        cmdParams.update({k:v for k,v in vars(args).items() if v}) # the optional params if supplied
        cmdParams.update({'relloc': relloc, 'absloc': join(self.outdir, relloc)})
        return cmdParams

    def _saveExpDotmrl(self, expDir, expConfig):
        # write .mrl file and save as current expId
        with open(join(expDir, '.mrl'),'w') as fh:
            json.dump(expConfig, fh, indent=2)
            fh.write("\n")

    def _checkValidExp(self, name):
        if len(name) != len(self._fmtSingleExp(0)): return False
        try:
            return self._fmtSingleExp(int(name)) == name
        except:
            return False

    def _loadExp(self, argExpId):
        expId = self._resolveExpId(argExpId)
        expDir = self._getExpDir(expId)
        expConfig = self._getExpConf(expId)
        # Load .mrl.cfg file if it exists
        try:
            with open(join(expDir, '.mrl.cfg')) as fh:
                bconf = json.load(fh, object_hook=_decode_dict)
                for k,v in bconf.iteritems():
                    setattr(cfg,k,v)
        except IOError: #file doesnt exist -> write a template
            open(join(expDir, '.mrl.cfg'),'w').write("{\n}\n")
        return (expId, expDir, expConfig)

    def _resolveExpId(self, expId):
        """ resolves expId from int, 'last' or path, and returns directory,
        or raise error if not found """
        if expId == 'last' and self.lastExpId is not None:
            return self.lastExpId
        elif type(expId) == int:
            if expId in self.expList:
                return expId
            else:
                raise InvalidExpIdException("Invalid experiment id (not in list): {}".format(int(expId)))
        elif expId.isdigit():
            if int(expId) in self.expList:
                return int(expId)
            else:
                raise InvalidExpIdException("Invalid experiment id (not in list): {}".format(int(expId)))
        elif isdir(expId) and relpath(expId, self.outdir) in self.expDirList:
            return self.expList[self.expDirList.index(relpath(expId, self.outdir))]
        else:
            raise InvalidExpIdException("This is not recognized as a experiment location: " + expId)

    def _getExpDir(self, expId, new=False):
        if not new and not expId in self.expList:
            raise InvalidExpIdException("Experiment {} not found.".format(expId))
        return join(self.outdir, self._fmtSingleExp(expId))

    def _newSubExp(self, expDir, subExpId, dotmrl, confContent):
        subExpDir = join(expDir, self._fmtSubExp(subExpId))
        os.mkdir(subExpDir)
        self._copyConfigFrom(expDir, subExpDir)
        with open(join(subExpDir, '.mrl'), 'w') as fh:
            json.dump(dotmrl, fh, indent=2)
            fh.write("\n")
        with open(join(subExpDir, cfg.confTemplFile), "w") as fh:
            fh.write(confContent)
            fh.write("\n")
    
    def _getExpConf(self, expId):
        with open(join(self._getExpDir(expId), '.mrl')) as fh:
            expConfig = json.JSONDecoder(object_pairs_hook=OrderedDict).decode(fh.read())
        return expConfig

    def _putEmptyNote(self, expDir, description):
        with open(join(expDir, '.mrl.note'),'w') as fh:
            if description:
                fh.write('### ' + description + '\n')
            fh.write('#### Goal\n\n#### Observations\n\n#### Conclusions\n')

def main():
    try:
        mrlState = MetaRunLog(os.getcwd())
    except InvalidOutDirException as e:
        print(e)
        return
    except NoBasedirConfig as e:
        parser = argparse.ArgumentParser(
                description='No valid .mrl.cfg file found. Choose init to initialize, \
                        or raiseException to see what went wrong.')
        subparsers = parser.add_subparsers(title='subcommands', description='valid subcommands')
        # init basedir
        parser_init = subparsers.add_parser('init', help='init current directory as basedir. Should typically be your git top-level dir.')
        parser_init.add_argument('outdir', default=cfg.outdir, help='where experiment run directories will be made and config/models files will be saved.')
        parser_init.set_defaults(mode='init')
        parser_raise = subparsers.add_parser('raise', help='Raise the NoBasedirConfig exception')
        parser_raise.set_defaults(mode='raise')
        args = parser.parse_args()
        if args.mode == 'init':
            try:
                print initBasedir(os.getcwd(), args)
            except InvalidOutDirException as e2:
                print(e2)
            return
        elif args.mode == 'raise':
            raise
    # Resume normal operation.
    parser = argparse.ArgumentParser(description='Metarunlog.')
    #mode_choices = [m for m in dir(MetaRunLog) if '_' not in m]
    #parser.add_argument('mode', metavar='mode', help='Mode to run metarunlog.', choices=mode_choices)
    subparsers = parser.add_subparsers(title='subcommands', description='valid subcommands')
    # new
    parser_new = subparsers.add_parser('new', help='new experiment directory.')
    parser_new.add_argument('-nc', '--notclean', action='store_const', const=True)
    parser_new.add_argument('-gfut', '--gitFailUntracked', choices=['no', 'yes'], default = cfg.gitFailUntrackedDefault)
    parser_new.add_argument('-cp', '--copyConfigFrom', default = 'last', nargs='?')
    parser_new.add_argument('description', help='Description', nargs='?')
    parser_new.set_defaults(mode='new')
    # info
    parser_info = subparsers.add_parser('info', help='show experiment info.')
    parser_info.add_argument('expId', default='last', help='exp number, directory, or last', nargs='?')
    parser_info.set_defaults(mode='info')
    parser_infosc = subparsers.add_parser('last', help='shortcut for mrl info last.')
    parser_infosc.set_defaults(mode='info', expId='last')
    # ls
    parser_ls = subparsers.add_parser('ls', help = 'list output dir, newest first.')
    parser_ls.add_argument('-tm', action='store_const', const=True, help='Show timestamp')
    parser_ls.add_argument('-ghash', action='store_const', const=True, help='Show git hash')
    parser_ls.add_argument('-gdesc', action='store_const', const=True, help='Show git description')
    parser_ls.add_argument('-desc', action='store_const', const=True, help='Show experiment description')
    parser_ls.set_defaults(mode='ls')
    # makebatch
    parser_batch = subparsers.add_parser('makebatch', help = 'make batch of config files from batch config template')
    parser_batch.add_argument('expId', help='experiment ID', default='last', nargs='?')
    parser_batch.add_argument('-replace', help='Overwrite config files if already expanded', action='store_const', const=True)
    parser_batch.set_defaults(mode='makebatch')
    # hpc Fetch
    parser_hpcFetch = subparsers.add_parser('hpcFetch', help = 'Fetch output logs and optionally data from hpc')
    parser_hpcFetch.add_argument('expId', help='experiment ID', default='last', nargs='?')
    parser_hpcFetch.add_argument('subExpId', help='subExperiment ID', default='all', nargs='?')
    parser_hpcFetch.add_argument('-data', help='Fetch hpc output data.', action='store_const', const=True)
    parser_hpcFetch.set_defaults(mode='hpcFetch')
    # whetlab parser
    parser_whetlab = subparsers.add_parser('whetlab', help = 'Hyper optimize through whetlab')
    parser_whetlab.add_argument('expId', help='experiment ID', default='last', nargs='?')
    parser_whetlab.add_argument('-resource', help='resource (cluster) to use', choices = cfg.resources.keys(), default='local')
    parser_whetlab.set_defaults(subExpId=None) # for makeJobList
    parser_whetlab.set_defaults(mode='whetlab')
    # job parsers , and add optvars to whetlab
    for jobName, commandList in cfg.jobs.iteritems():
        optVars = mrlState.jobOptVars[jobName]
        parser_job = subparsers.add_parser(jobName, help = 'job cmd {} from your .mrl.cfg file'.format(jobName))
        parser_job.add_argument('expId', help='experiment ID', default='last', nargs='?')
        parser_job.add_argument('subExpId', help='subExperiment ID: all, single (no makebatch expansion), or a specific subexpid. default: all', default='all', nargs='?')
        parser_job.add_argument('-resource', help='resource (cluster) to use', choices = cfg.resources.keys(), default='local')
        for varName in optVars:
            parser_job.add_argument('-'+varName)
            if jobName == cfg.whetlab['jobName']:
                parser_whetlab.add_argument('-'+varName)
        parser_job.set_defaults(mode='runJobs')
        parser_job.set_defaults(jobName=jobName)
    # analyze
    parser_Analyze = subparsers.add_parser('analyze', help = 'Analyze expId by running the functions from analyze module, specified in .mrl.cfg')
    parser_Analyze.add_argument('expId', help='experiment ID', default='last', nargs='?')
    parser_Analyze.add_argument('-outdir', help='path to output directory, default: expDir/analysis/')
    parser_Analyze.set_defaults(mode='analyze')
    #PARSE
    args = parser.parse_args()
    try:
        ret = getattr(mrlState, args.mode)(args)
        if ret: print(ret)
    except (NoCleanStateException,\
            InvalidExpIdException,\
            BatchException,\
            ConfParserException,\
            HpcException,\
            NoSuchJobException,\
            JobException,\
            SchedulerException) as e:
        print(e)
    except Exception as e:
        print "Unchecked exception"
        raise
