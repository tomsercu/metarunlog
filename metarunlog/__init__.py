#!/usr/bin/env python
# Metarunlog, experiment management tool.
# Author: Tom Sercu
# Date: 2015-01-23

import metarunlog.cfg as cfg # NOTE cfg is modified by MetaRunLog._loadBasedirConfig() with custom configuration.
import os
import sys
from os import listdir
from os.path import isdir, isfile, join, relpath, expanduser
import argparse
import subprocess
import json
import pdb
import datetime
from collections import OrderedDict
from shutil import copy as shcopy
from jinja2 import Template, Environment, meta
import itertools
import getpass

DEBUG = True

class InvalidOutDirException(Exception):
    pass
class NoCleanStateException(Exception):
    pass
class NoBasedirConfig(Exception):
    def __init__(self, basedir, e):
        self.basedir = basedir
        self.orig_e = e
    def __str__(self):
        return "NoBasedirConfig in {} : {}".format(self.basedir, self.orig_e)
class InvalidExpIdException(Exception):
    pass
class BatchException(Exception):
    pass
class HpcException(Exception):
    pass
class NoSuchCustomCommandException(Exception):
    pass

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

class BatchParser:
    """
    BatchParser class is initialized with batch-template (list of lines)
    including the last lines determining the values,
    and generates self.output as a list of strings (that can be written to file).
    """
    def __init__(self, template):
        grid = OrderedDict()
        params = [{}]
        # iterate over last lines and parse them to collect grid parameters.
        # correct formatting of mrl instructions:
        # [something] MRL:grid['key'] = [vallist]
        # where [something] is comment symbol. The space after it is essential.
        for line in template[::-1]:
            if not line.strip(): continue
            line = line.split(None, 1)[-1].split(":",1) #discard comment symbol
            if line[0] != 'MRL': break
            exec(line[1])
        # construct output params list
        keys = grid.keys()
        vals = list(itertools.product(*[grid[k] for k in keys]))
        self.params = [dict(zip(keys, v)) for v in vals]
        self.params = [dict(d1.items() + d2.items()) for d1,d2 in itertools.product(self.params, params)]
        # render the templates
        self.output = []
        jtmpl = Template("".join(template))
        for i, param in enumerate(self.params):
            self.output.append((i+1, param, jtmpl.render(**param)))

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
        self.hpcPass = None
        # parse the custom commands into templates and extract the optional arguments for argparse
        self.jEnv = Environment()
        self.customTemplates = {customName:[]  for customName in cfg.custom.keys()}
        self.customOptVars = {customName:set() for customName in cfg.custom.keys()}
        for customName, cList in cfg.custom.iteritems():
            for cmdEnv in cList:
                self.customTemplates[customName].append({envKey: self.jEnv.from_string(cmd) for envKey, cmd in cmdEnv.iteritems()})
                for cmd in cmdEnv.values():
                    self.customOptVars[customName].update(meta.find_undeclared_variables(self.jEnv.parse(cmd)))

    def _loadBasedirConfig(self):
        try:
            with open(join(self.basedir, '.mrl.cfg')) as fh:
                bconf = json.load(fh)
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
        expConfig['timestamp'] = datetime.datetime.now().isoformat().split('.')[0]
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
        self._renderLaunchScript(expDir, expConfig, self._fmtLaunchScriptFile(expId))
        self._putEmptyNote(expDir, expConfig['description'])
        self.lastExpId = expId
        return expDir

    def info(self, args):
        """ load info from experiment id and print it """
        expId, expDir, expConfig = self._loadExp(args.expId)
        items = ['',expDir,'']
        maxkeylen = max(len(k) for k,v in expConfig.iteritems())
        items += ["%*s : %.80s" % (maxkeylen,k,str(v)) for k,v in expConfig.iteritems()]
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
        # resolve id
        expId, expDir, expConfig = self._loadExp(args.expId)
        # check if already expanded in batch and cancel
        oldBatchList = []
        if 'batchlist' in expConfig:
            if args.replace:
                oldBatchList = expConfig['batchlist']
            else:
                raise BatchException("Experiment {} is already expanded into a batch of length {}".\
                        format(expId, len(expConfig['batchlist'])))
        # make BatchParser object
        try:
            with open(join(expDir, cfg.batchTemplFile)) as fh:
                bp = BatchParser(fh.readlines())
        except jinja2.exceptions.TemplateSyntaxError as e:
            err = "TemplateSyntaxError in your {} template file: \n {}".format(cfg.batchTemplFile, str(e))
            raise BatchException(err)
        # check if BatchParser output is non-empty
        if not bp.output:
            err = "BatchParser output is empty, are you sure {} is a batch template?"
            err = err.format(join(expDir, cfg.batchTemplFile))
            raise BatchException(err)
        # generate output directories, write the output config files
        expConfig['batchlist'] = []
        for i, params, fileContent in bp.output:
            expConfig['batchlist'].append(params)
            subExpDir = join(expDir, self._fmtBatchExp(expId=expId, subExpId=i))
            if i > len(oldBatchList):
                os.mkdir(subExpDir)
            self._copyConfigFrom(expDir, subExpDir)
            with open(join(subExpDir, cfg.batchTemplFile), "w") as fh:
                fh.write(fileContent)
                fh.write("\n")
            self._renderLaunchScript(subExpDir, expConfig, self._fmtLaunchScriptFile(expId, i))

        # update the current .mrl file
        self._saveExpDotmrl(expDir, expConfig)
        self._writeqsubFile(expId, len(bp.output))
        try:
            os.remove(join(expDir, self._fmtLaunchScriptFile(expId))) # this conf is a template so doesnt make sense to run it
        except OSError:
            pass
        return "Succesfully generated config files for expId {}.\n{}".format(expId,expConfig['batchlist'])

    def hpcSubmit(self, args):
        # TODO Use custom() for this. Add remote setting for custom
        expId, expDir, expConfig = self._loadExp(args.expId)
        remoteExpDir = join(cfg.hpcBasedir, cfg.outdir, self._fmtSingleExp(expId))
        if 'hpcSubmit' in expConfig and not args.replace:
            raise HpcException("hpcSubmit key already in {} .mrl file. Aborting to avoid data loss.".format(expId))
        # scp to copy to remote
        try:
            self._hpc("mkdir {}".format(remoteExpDir))
        except Exception as e:
            if not args.replace:
                raise HpcException("hpc submission - error in mkdir returned nonzero exit. Dir already exists?")
        self._hpc("scp -r {} {}:{}".format(join(expDir,'*'), cfg.hpcServer, remoteExpDir), ssh=False)
        # subprocess ssh then qsub then print qstat
        if 'batchlist' in expConfig:
            hpcRet = self._hpc('cd {}; ./{}'.format(remoteExpDir, cfg.qsubFile))
            print hpcRet.strip().split("\n")
            # every even-indexed line is an id
            try:
                qsubids = [int(x) for i,x in enumerate(hpcRet.strip().split("\n")) if i%2==0]
            except Exception as e: #failure on qsub? save output
                print "Couldn't save qsubids correctly: ", e
                qsubids = hpcRet
        else:
            hpcRet = self._hpc('cd {}; qsub {}'.format(remoteExpDir, self._fmtLaunchScriptFile(expId)))
            print hpcRet
            qsubids = int(hpcRet)
        expConfig['hpcSubmit'] = qsubids
        self._saveExpDotmrl(expDir, expConfig)

    def hpcFetch(self, args):
        expId, expDir, expConfig = self._loadExp(args.expId)
        remoteExpDir = join(cfg.hpcBasedir, cfg.outdir, self._fmtSingleExp(expId))
        if 'hpcSubmit' not in expConfig:
            raise HpcException("hpcSubmit key not in in {} .mrl file. Was this launched as hpc job?".format(expId))
        # Locations to fetch from
        runLocs = self._getRunLocations(expId, args.subExpId, expConfig, relativeTo=expDir)
        # Exclude datafiles ifneeded
        if not args.data:
            excludes = " ".join(['--exclude={}'.format(datafile) for datafile in cfg.hpcOutputData])
        else:
            excludes = ""
        for loc in runLocs:
            cmd = "rsync -aP {} {}:{}/ {}/".format(excludes, cfg.hpcServer, join(remoteExpDir,loc), join(expDir,loc))
            self._hpc(cmd, ssh=False)

    def custom(self, args):
        expId, expDir, expConfig = self._loadExp(args.expId)
        customName = args.customName
        cmdTemplates = self.customTemplates[customName]
        runLocs = self._getRunLocations(expId, args.subExpId, expConfig, relativeTo=self.outdir)
        originalCwd = os.getcwd() # self.basedir if ran through ./mrl
        cmdParams = {'mrlOutdir': self.outdir, 'mrlBasedir': self.basedir}
        cmdParams.update(expConfig)
        cmdParams.update({k:v for k,v in vars(args).items() if v}) # the optional params if supplied
        # Render & run the commands for all experiments
        for relloc in runLocs:
            absloc = join(self.outdir, relloc)
            print "{} for location {}".format(customName, relloc)
            # Make location cmdParams
            cmdParams.update({'relloc': relloc, 'absloc': absloc})
            # Execute commands in their environment
            for cmdEnvTemplate in cmdTemplates:
                cmdEnv = {k:tmpl.render(cmdParams) for k,tmpl in cmdEnvTemplate.items()}
                if 'cwd' in cmdEnv:
                    os.chdir(os.path.expanduser(cmdEnv['cwd']))
                print cmdEnv['command']
                stdout = open(join(absloc, cmdEnv['output']),"w") if 'output' in cmdEnv else None
                subprocess.call(cmdEnv['command'], stdout=stdout, shell=True)
                if 'cwd' in cmdEnv:
                    os.chdir(originalCwd)

    def analyze(self, args):
        import pandas as pd
        import analyze
        expId, expDir, expConfig = self._loadExp(args.expId)
        print "Analyze expId {} in path {}".format(expId, expDir)
        outdir = args.outdir if args.outdir else join(expDir, 'analysis')
        if not os.path.exists(outdir): os.mkdir(outdir)
        # load the params into dataframe
        isBatch = 'batchlist' in expConfig
        if isBatch:
            batchlist = expConfig['batchlist']
            subExpIds = [self._fmtBatchExp(expId, i) for i in range(1,len(batchlist)+1)]
            Dparams = pd.DataFrame(batchlist, index=subExpIds)
        outhtml = analyze.HtmlFile()
        title = 'Experiment {} - {}'.format(cfg.singleExpFormat.format(expId=expId), expConfig['timestamp'].split('T')[0])
        if 'description' in expConfig and expConfig['description']: title += ' - ' + expConfig['description']
        outhtml.addTitle(title)
        outhtml.parseNote(join(expDir,'.mrl.note'))
        # TODO keep analysis functions in order by using ordereddict in .mrl.cfg and cfg.py
        if isBatch:
            # analysis_overview functions
            for funcname, xtrargs in cfg.analysis_overview.items():
                outhtml.addHeader('{} - {}'.format('overview', funcname), 1)
                retval = getattr(analyze, funcname)(expDir, outdir, subExpIds, Dparams, *xtrargs)
                outhtml.addRetVal(retval)
        # per exp functions
        if isBatch:
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

    def _hpc(self, cmd, ssh=True):
        if not self.hpcPass:
            self.hpcPass= getpass.getpass("Password for hpc: ")
        if ssh:
            sshcmd = "ssh {}".format(cfg.hpcServer)
            cmd = '"{}"'.format(cmd.replace('"', '\\"'))
        else:
            sshcmd = ""
        mcmd = "sshpass -p '{}' {} {}".format(self.hpcPass, sshcmd, cmd)
        cleancmd = "sshpass -p '{}' {} {}".format('***', sshcmd, cmd)
        if DEBUG: print cleancmd
        try:
            out = subprocess.check_output(mcmd, shell=True)
        except subprocess.CalledProcessError as e:
            # remove pwd from cmd
            err = str(e).replace(mcmd, cleancmd)
            raise HpcException(err)
        return out

    def _getRunLocations(self, expId, subExpId, expConfig, relativeTo=''):
        if 'batchlist' in expConfig:
            if subExpId == 'all':
                locs = [self._fmtBatchExp(expId, i) for i in range(1,len(expConfig['batchlist'])+1)]
            elif subExpId.isdigit():
                if int(subExpId) > len(expConfig['batchlist']):
                    raise SubExpIdException("subExpId {} out of range (batch size {} in expConfig)".format(subExpId,len(expConfig['batchlist'])))
                locs = [self._fmtBatchExp(expId, int(subExpId)), ]
            else:
                # TODO list of subexpids can be handy
                raise SubExpIdException("Don't understand subExpId {}.".format(subExpId))
        else:
            locs = ['']
        expDir = self._getExpDir(expId)
        if relativeTo != expDir:
            locs = [join(expDir, loc) for loc in locs]
            if relativeTo:
                locs = [relpath(loc, relativeTo) for loc in locs]
        return locs

    def _writeqsubFile(self, expId, N):
        # TODO make git clone  and checkout part of this to avoid 100 clones to the subdirs.
        expDir = self._getExpDir(expId)
        command = 'cd {} && qsub {} && cd .. && sleep 0.01 && echo "qsubbed {}"'
        subdirs = [self._fmtBatchExp(expId=expId, subExpId=i) for i in range(1,N+1)]
        lsfiles = [self._fmtLaunchScriptFile(expId, i) for i in range(1,N+1)]
        cmds = [command.format(subdir, lsfile, subdir) for lsfile,subdir in zip(lsfiles,subdirs)]
        cmds.append("")
        open(join(expDir, cfg.qsubFile),"w").write("\n".join(cmds))
        os.chmod(join(expDir, cfg.qsubFile), 0770)

    def _renderLaunchScript(self, expDir, expConfig, fn):
        """ Launch script is jinja template in basedir config.
        It has access to expDir, the global configuration,
        and all experiment specific variables
        in expConfig."""
        # TODO make git clone and checkout part optional here
        jtemp = Template(cfg.launchScriptTempl)
        tparams = {k:getattr(cfg, k) for k in dir(cfg) if '_' not in k}
        tparams.update(expConfig)
        tparams['expDir'] = relpath(expDir, self.basedir)
        tparams['basedir']= self._relpathUser(self.basedir)
        with open(join(expDir, fn), "w") as fh:
            fh.write(jtemp.render(tparams))
            fh.write("\n")
        os.chmod(join(expDir, fn), 0770)

    def _fmtSingleExp(self, expId):
        # TODO change fmtSingleExp to fetch date from a list initialized in init, then fill in that date here.
        return cfg.singleExpFormat.format(expId=expId)

    def _fmtBatchExp(self, expId, subExpId):
        return cfg.batchExpFormat.format(expId=expId, subExpId=subExpId)

    def _fmtLaunchScriptFile(self,expId, subExpId=None):
        if subExpId:
            return cfg.launchScriptFile.format(self._fmtBatchExp(expId, subExpId))
        else:
            return cfg.launchScriptFile.format(self._fmtSingleExp(expId))

    def _relpathUser(self, path):
        return '~/' + relpath(path, expanduser('~'))

    def _copyConfigFrom(self, src, dst):
        for cfn in cfg.copyFiles:
            shcopy(join(src,cfn), join(dst, cfn))

    def _saveExpDotmrl(self, expDir, expConfig):
        # write .mrl file and save as current expId
        with open(join(expDir, '.mrl'),'w') as fh:
            json.dump(expConfig, fh, indent=2)
            fh.write("\n")

    def _checkValidExp(self, name):
        # TODO change
        if len(name) != len(self._fmtSingleExp(0)): return False
        try:
            int(name)
        except:
            return False
        # parse each .mrl file in subdir? Probably overkill
        return True

    def _loadExp(self, argExpId):
        expId = self._resolveExpId(argExpId)
        expDir = self._getExpDir(expId)
        expConfig = self._getExpConf(expId)
        # Load .mrl.cfg file if it exists
        try:
            with open(join(expDir, '.mrl.cfg')) as fh:
                bconf = json.load(fh)
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
    # hpc Submit
    parser_hpcSubmit = subparsers.add_parser('hpcSubmit', help = 'scp output folder to hpc and run it by qsubbing')
    parser_hpcSubmit.add_argument('expId', help='experiment ID', default='last', nargs='?')
    parser_hpcSubmit.add_argument('-replace', help='Ignore existing hpc data.', action='store_const', const=True)
    parser_hpcSubmit.set_defaults(mode='hpcSubmit')
    # hpc Fetch
    parser_hpcFetch = subparsers.add_parser('hpcFetch', help = 'Fetch output logs and optionally data from hpc')
    parser_hpcFetch.add_argument('expId', help='experiment ID', default='last', nargs='?')
    parser_hpcFetch.add_argument('subExpId', help='subExperiment ID', default='all', nargs='?')
    parser_hpcFetch.add_argument('-data', help='Fetch hpc output data.', action='store_const', const=True)
    parser_hpcFetch.set_defaults(mode='hpcFetch')
    # custom
    custom_parsers = []
    for customName, commandList in cfg.custom.iteritems():
        optVars = mrlState.customOptVars[customName]
        parser_custom = subparsers.add_parser(customName, help = 'custom cmd {} from your .mrl.cfg file'.format(customName))
        parser_custom.add_argument('expId', help='experiment ID', default='last', nargs='?')
        parser_custom.add_argument('subExpId', help='subExperiment ID', default='all', nargs='?')
        for varName in optVars:
            parser_custom.add_argument('-'+varName)
        parser_custom.set_defaults(mode='custom')
        parser_custom.set_defaults(customName=customName)
        custom_parsers.append(parser_custom)
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
            HpcException,
            NoSuchCustomCommandException) as e:
        print(e)
    except Exception as e:
        print "Unchecked exception"
        raise
