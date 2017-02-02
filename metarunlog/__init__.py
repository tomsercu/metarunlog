#!/usr/bin/env python
# Metarunlog, experiment management tool.
# Author: Tom Sercu
# Date: 2015-01-23

from metarunlog import cfg # NOTE cfg is modified by MetaRunLog._loadBasedirConfig() with custom configuration.
from metarunlog.exceptions import *
from metarunlog.util import nowstring, sshify, _decode_dict, _decode_list, get_commit
from metarunlog.confParser import ConfParser
import os
import sys
import math
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
import jinja2
from jinja2 import Template, Environment, meta
import itertools
import getpass

DEBUG = True

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
        self.expList.append(expId)
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
                expDir = self._getExpDir(expId)
                row += "\t" + self._expIsDoneIndicator(expDir) + expConfig['description']
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

    def analyze(self, args):
        ## Load modules only needed for analyzing and rendering the html file
        import pandas as pd
        import renderHtml
        try:
            import mrl_analyze
        except Exception as e:
            print("Could not load local mrl_analyze module: {}".format(str(e)))
        expId, expDir, expConfig = self._loadExp(args.expId)
        print "Analyze expId {} in path {}".format(expId, expDir)
        outdir = args.outdir if args.outdir else join(expDir, 'analysis')
        if not os.path.exists(outdir): os.mkdir(outdir)
        # load the params into dataframe
        subExpIds = self._getSubExperiments(expDir)
        if subExpIds:
            try:
                paramList = [self._loadSubExp(join(expDir,subExpId))['params'] for subExpId in subExpIds]
            except (IOError, KeyError) as e: # dummy
                paramList = [{'subExpId': subExpId} for subExpId in subExpIds]
            Dparams = pd.DataFrame(paramList, index=subExpIds)
        outhtml = renderHtml.HtmlFile()
        title = '{} {} - {}'.format(cfg.name, cfg.singleExpFormat.format(expId=expId), expConfig['timestamp'].split('T')[0])
        if 'description' in expConfig and expConfig['description']: title += ' - ' + expConfig['description']
        outhtml.addTitle(self._expIsDoneIndicator(expDir) + title)
        outhtml.parseNote(join(expDir, cfg.note_fn))
        # TODO keep analysis functions in order by using ordereddict in .mrl.cfg and cfg.py
        if subExpIds:
            # analysis_overview functions
            for funcname, xtrargs in sorted(cfg.analysis_overview.items()):
                outhtml.addHeader('{} - {}'.format('overview', funcname), 1)
                retval = getattr(mrl_analyze, funcname)(expDir, outdir, subExpIds, Dparams, *xtrargs)
                outhtml.addRetVal(retval)
        # per exp functions
        if subExpIds:
            for subExpId in subExpIds:
                subExpDir = join(expDir, subExpId)
                outhtml.addHeader('{} - {}'.format('subExp', subExpId), 1)
                for funcname, xtrargs in cfg.analysis_subexp.items():
                    outhtml.addHeader('{}'.format(funcname), 2)
                    retval = getattr(mrl_analyze, funcname)(subExpDir, outdir, Dparams, subExpId, *xtrargs)
                    outhtml.addRetVal(retval)
        else:
            for funcname, xtrargs in cfg.analysis_subexp.items():
                outhtml.addHeader('{}'.format(funcname), 1)
                retval = getattr(mrl_analyze, funcname)(expDir, outdir, None, 'def', *xtrargs)
                outhtml.addRetVal(retval)
        outhtml.render(join(outdir, 'index.html'))
        if cfg.analysis_webdir:
            webdir = join(cfg.analysis_webdir, self._fmtSingleExp(expId))
            #if not os.path.exists(webdir):
                #os.mkdir(webdir)
            subprocess.call("rsync -az {}/* {}/".format(outdir, webdir), shell=True)
            #subprocess.call("chmod -R a+r {}".format(webdir), shell=True)
            #subprocess.call(r"find %s -type d -exec chmod a+x {} \;"%(webdir), shell=True)
            print "Copied to webdir {}".format(webdir)

    def execWithHooks(self, mode, args):
        noneFunc   = lambda x:None # empty dummy func
        hookBefore = getattr(self, 'before_' + args.mode, noneFunc)
        hookAfter  = getattr(self, 'after_'  + args.mode, noneFunc)
        # NOTE each hook before/after/func itself has to get expId, expDir from args itself.
        hookBefore(args)
        ret = getattr(self, args.mode)(args)
        hookAfter(args)
        return ret

    def _loadSubExp(self, subExpDir):
        with open(join(subExpDir, '.mrl')) as fh:
            return json.load(fh, object_hook=_decode_dict)

    def _getSubExperiments(self, expDir):
        """ returns a list of the existing subexperiments as formatted strings """
        subexp = []
        for subdir in sorted(listdir(expDir)):
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
        with open(join(expDir, cfg.note_fn),'w') as fh:
            if description:
                fh.write('### ' + description + '\n')
            fh.write('#### Goal\n\n#### Observations\n\n#### Conclusions\n')

    def _expIsDone(self, expDir):
        return os.path.exists(os.path.join(expDir, '.mrl.done'))

    def _expIsDoneIndicator(self, expDir):
        return '   ' if  self._expIsDone(expDir) else '** '

def main():
    try:
        sys.path.append(os.getcwd()) # include modules in basedir like myAnalyze
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
    # No Exception: Resume normal operation.
    # Extend MetaRunLog with mrl_hooks
    try:
        import mrl_hooks # from basedir, user-supplied
        for hook in cfg.hooks:
            setattr(MetaRunLog, hook, getattr(mrl_hooks, hook))
    except ImportError:
        print('Warning: no valid mlr_hooks.py file - will ignore cfg.hooks')
        mrl_hooks = None
    # CL menu
    parser = argparse.ArgumentParser(description='Metarunlog.')
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
    # analyze
    parser_Analyze = subparsers.add_parser('analyze', help = 'Analyze expId by running the functions from analyze module, specified in .mrl.cfg')
    parser_Analyze.add_argument('expId', help='experiment ID', default='last', nargs='?')
    parser_Analyze.add_argument('-outdir', help='path to output directory, default: expDir/analysis/')
    parser_Analyze.set_defaults(mode='analyze')
    # functions registered as standalone hooks
    if mrl_hooks:
        for hook in cfg.hooks:
            if 'before_' in hook or 'after_' in hook:
                continue
            parser_hook = subparsers.add_parser(hook, help = 'custom function from mrl_hooks.py')
            parser_hook.add_argument('expId', help='experiment ID', default='last', nargs='?')
            for xarg, defaultval in cfg.hooks[hook].iteritems():
                if defaultval:
                    parser_hook.add_argument('-' + xarg, default=defaultval, help='optional xarg, default: {}'.format(defaultval), nargs='?')
                else: # named argument, yet required. Slightly bad form.
                    parser_hook.add_argument('-' + xarg, help='required xarg', required=True) #, nargs='?')
            parser_hook.set_defaults(mode=hook)
    #PARSE
    args = parser.parse_args()
    try:
        ret = mrlState.execWithHooks(args.mode, args)
        if ret: print(ret)
    except (NoCleanStateException,\
            InvalidExpIdException,\
            BatchException,\
            ConfParserException) as e:
        print(e)
    except Exception as e:
        print "Unchecked exception"
        raise
