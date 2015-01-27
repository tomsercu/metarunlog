#!/usr/bin/env python
# Metarunlog, experiment management tool.
# Author: Tom Sercu
# Date: 2015-01-23

import metarunlog.cfg as cfg
import os
import sys
from os import listdir
from os.path import isdir, isfile, join
import argparse
import subprocess
import json
import pdb
import datetime

DEBUG = True

class InvalidDirException(Exception):
    pass
class NoCleanStateException(Exception):
    pass
class NoBasedirConfig(Exception):
    def __init__(self, basedir):
        self.basedir = basedir
class InvalidExpIdException(Exception):
    pass

def get_commit():
    cline = subprocess.check_output("git log -n1 --oneline", shell=True)
    #print "cline: ", cline
    cline = cline.split()
    return (cline[0], "".join(cline[1:]))

def needsBasedirConfig(func):
    def wrapper(self, *args, **kwargs):
        if not self.basedirConfig:
            raise NoBasedirConfig(self.basedir)
        else:
            func(self, *args, **kwargs)
    return wrapper

class MetaRunLog:
    """
    Metarunlog state from which all actions are coordinated.
    Needs to be run from a valid basedir (with .mrl.cfg file).
    Initialization overwrites cfg module from .mrl.cfg: metarunlog.cfg.py should be
    seen as a template for .mrl.cfg.
    """
    def __init__(self, basedir):
        self.basedir = basedir
        self.basedirConfig = self._loadBasedirConfig()
        self.outdir  = join(self.basedir, cfg.outdir)
        if not isdir(self.outdir): raise InvalidDirException("Need output directory " + self.outdir)
        self.expList = sorted([int(x) for x in listdir(self.outdir) if self._checkValidExp(x)])
        self.lastExpId = None if not self.expList else self.expList[-1]

    def _loadBasedirConfig(self):
        try:
            with open(join(self.basedir, '.mrl.cfg')) as fh:
                bconf = json.load(fh)
                for k,v in bconf.iteritems():
                    cfg.k = v
            return True
        except Exception as e:
            print "could not load BasedirConfig: ", e
            return False

    def initBasedir(self, args):
        if self.basedirConfig:
            raise Exception("{} already has valid .mrl.cfg file, don't try to re-init.".format(self.basedir))
        with open(join(self.basedir, '.mrl.cfg'),"w") as fh:
            # copy the cfg attributes into ordered dict
            bconf = {k:getattr(cfg,k) for k in dir(cfg) if '__' not in k}
            bconf['outdir'] = args.outdir
            json.dump(bconf, fh, indent=2)
            fh.write("\n")
        self.basedirConfig = self._loadBasedirConfig()
        print self.basedirConfig
        if not self.basedirConfig:
            raise Exception("Failed to init basedirconfig")

    @needsBasedirConfig
    def new(self,args):
        expId = 1 if self.lastExpId is None else self.lastExpId+1
        expConfig = OrderedDict()
        expConfig ['expId'] = expId
        expConfig['basedir'] = self.basedir
        gitclean = ('notclean' not in args)
        expConfig['untracked']= args.gitFailUntracked
        uncommited = subprocess.check_output("git status --porcelain --untracked=" + expConfig['untracked'], shell=True)
        #print "uncommited: ", uncommited
        if gitclean and uncommited: raise NoCleanStateException("new: uncommited files -- please commit changes first " + uncommited)
        expConfig['gitHash'], expConfig['gitDescription'] = get_commit()
        if not gitclean and uncommited: expConfig['gitHash'] += '-sloppy'
        expConfig['timestamp'] = datetime.datetime.now().isoformat().split('.')[0]
        # make dir and save .mrl
        expDir = self._getExpDir(expId, True)
        os.mkdir(expDir)
        # copy config files

        # write .mrl file and save as current expId
        with open(join(expDir, '.mrl'),'w') as fh:
            json.dump(expConfig, fh, indent=2)
            fh.write("\n")
        self.lastExpId = expId
        return expDir

    @needsBasedirConfig
    def info(self, args):
        """ load info from experiment id and print it """
        with open(self._getExpDir(args.expId)) as fh:
            expConfig = json.load(fh)
            s = "\n".join("{} : {}".format(k,v) for k,v in expConfig.iteritems())
        return s

    def _checkValidExp(self, name):
        if len(name) != len(cfg.singleExpFormat.format(exp=0)): return False
        try:
            int(name)
        except:
            return False
        # parse each .mrl file in subdir? Probably overkill
        return True

    def _getExpDir(self, expId, new=False):
        if not new and not expId in self.expList:
            raise InvalidExpIdException("Experiment {} not found.".format(args.expId))
        return join(self.outdir, cfg.singleExpFormat.format(expId=expId))

def main():
    parser = argparse.ArgumentParser(description='Metarunlog.')
    #mode_choices = [m for m in dir(MetaRunLog) if '_' not in m]
    #parser.add_argument('mode', metavar='mode', help='Mode to run metarunlog.', choices=mode_choices)
    subparsers = parser.add_subparsers(title='subcommands', description='valid subcommands')
    # init basedir
    parser_init = subparsers.add_parser('init', help='init current directory as basedir. Should typically be your git top-level dir.')
    parser_init.add_argument('outdir', default=cfg.outdir, help='where experiment run directories will be made and config/models files will be saved.')
    parser_init.set_defaults(mode='initBasedir')
    # new
    parser_new = subparsers.add_parser('new', help='new experiment directory.')
    parser_new.add_argument('-nc', '--notclean', action='store_const', const=True)
    parser_new.add_argument('-gfut', '--gitFailUntracked', choices=['no', 'yes'], default = cfg.gitFailUntrackedDefault)
    parser_new.add_argument('-cp', '--copyConfigFrom', default = 'last')
    parser_new.add_argument('description', help='Description')
    parser_new.set_defaults(mode='new')
    # info
    parser_info = subparsers.add_parser('info', help='show experiment info.')
    parser_info.add_argument('expId')
    parser_info.set_defaults(mode='info')
    args = parser.parse_args()
    if DEBUG: print args
    try:
        mrlState = MetaRunLog(os.getcwd())
    except InvalidDirException as e:
        print(e)
    else:
        try:
            print getattr(mrlState, args.mode)(args)
        except NoCleanStateException as e:
            print(e)
        except NoBasedirConfig as e:
            print "No basedir config file in {}".format(e.basedir)
            print "Run mrl init in this directory first to make it a base directory."
        except Exception as e:
            print "Unchecked exception"
            raise
