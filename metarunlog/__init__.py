#!/usr/bin/env python
# Metarunlog, experiment management tool.
# Author: Tom Sercu
# Date: 2015-01-23

import metarunlog.cfg as cfg
import os
import sys
from os import listdir
from os.path import isdir, isfile, join, relpath
import argparse
import subprocess
import json
import pdb
import datetime
from collections import OrderedDict
import shutil

DEBUG = True

class InvalidOutDirException(Exception):
    pass
class NoCleanStateException(Exception):
    pass
class NoBasedirConfig(Exception):
    def __init__(self, basedir, e):
        self.basedir = basedir
        self.orig_e = e
class InvalidExpIdException(Exception):
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
        return "{} already has valid .mrl.cfg file, don't try to re-init.".format(basedir)
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
        if not isdir(self.outdir): raise InvalidOutDirException("Need output directory " + self.outdir)
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
            raise NoBasedirConfig(self.basedir, str(e))

    def new(self,args):
        expId = 1 if self.lastExpId is None else self.lastExpId+1
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
        expConfig['shortDescription'] = args.description if args.description else ""
        expConfig['longDescription'] = "" # edit into .mrl file directly
        # make dir and symlink  and
        expDir = self._getExpDir(expId, True)
        os.remove(join(self.outdir,'last'))
        os.symlink(relpath(expDir,self.outdir), join(self.outdir, 'last'))
        os.mkdir(expDir)
        # After this point: expDir is made, no more exception throwing! copy config files
        try:
            if args.copyConfigFrom is None:
                pass
            elif args.copyConfigFrom == 'last' and self.lastExpId is not None:
                self._copyConfigFrom(self._getExpDir(self.lastExpId), expDir)
            elif args.copyConfigFrom.isdigit():
                self._copyConfigFrom(self._getExpDir(int(args.copyConfigFrom)), expDir)
            elif isdir(args.copyConfigFrom): #directory
                self._copyConfigFrom(args.copyConfigFrom, expDir)
            else:
                raise InvalidExpIdException("This is not recognized as a copyConfigFrom location: " + args.copyConfigFrom)
        except (InvalidExpIdException, IOError) as e:
            print("Can't copy config files. " + str(e))
            print("Still succesfully created new experiment directory.")
        # write .mrl file and save as current expId
        with open(join(expDir, '.mrl'),'w') as fh:
            json.dump(expConfig, fh, indent=2)
            fh.write("\n")
        self.lastExpId = expId
        return expDir

    def info(self, args):
        """ load info from experiment id and print it """
        expConfig = self._getExpConf(args.expId)
        return "\n".join("{} : {}".format(k,v) for k,v in expConfig.iteritems())

    def ls(self, args):
        for expId in self.expList[::-1]:
            expConfig = self._getExpConf(expId)
            row = cfg.singleExpFormat.format(expId=expId)
            if args.tm:
                row += "\t" + expConfig['timestamp']
            if args.ghash:
                row += "\t" + expConfig['gitHash']
            if args.gdesc:
                row += "\t" + expConfig['gitDescription']
            if args.desc:
                row += "\t" + expConfig['shortDescription']
            print row
        return ""

    def _copyConfigFrom(self, src, dst):
        for cfn in cfg.copyFiles:
            shutil.copy(join(src,cfn), join(dst, cfn))

    def _checkValidExp(self, name):
        if len(name) != len(cfg.singleExpFormat.format(expId=0)): return False
        try:
            int(name)
        except:
            return False
        # parse each .mrl file in subdir? Probably overkill
        return True

    def _getExpDir(self, expId, new=False):
        if not new and not expId in self.expList:
            raise InvalidExpIdException("Experiment {} not found.".format(expId))
        return join(self.outdir, cfg.singleExpFormat.format(expId=expId))
    def _getExpConf(self, expId):
        with open(join(self._getExpDir(expId), '.mrl')) as fh:
            expConfig = json.JSONDecoder(object_pairs_hook=OrderedDict).decode(fh.read())
        return expConfig

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
    parser_new.add_argument('-cp', '--copyConfigFrom', default = None)
    parser_new.add_argument('description', help='Description', nargs='?')
    parser_new.set_defaults(mode='new')
    # info
    parser_info = subparsers.add_parser('info', help='show experiment info.')
    parser_info.add_argument('expId', type=int)
    parser_info.set_defaults(mode='info')
    # ls
    parser_ls = subparsers.add_parser('ls', help = 'list output dir, newest first.')
    parser_ls.add_argument('-tm', action='store_const', const=True, help='Show timestamp')
    parser_ls.add_argument('-ghash', action='store_const', const=True, help='Show git hash')
    parser_ls.add_argument('-gdesc', action='store_const', const=True, help='Show git description')
    parser_ls.add_argument('-desc', action='store_const', const=True, help='Show experiment description')
    parser_ls.set_defaults(mode='ls')
    # TODO batch

    #PARSE
    args = parser.parse_args()
    if DEBUG: print args
    if args.mode == 'initBasedir':
        try:
            print initBasedir(os.getcwd(), args)
        except InvalidOutDirException as e:
            print(e)
        return
    try:
        mrlState = MetaRunLog(os.getcwd())
    except InvalidOutDirException as e:
        print(e)
        return
    else:
        try:
            ret = getattr(mrlState, args.mode)(args)
            if ret: print(ret)
        except NoCleanStateException as e:
            print(e)
        except NoBasedirConfig as e:
            print "No valid basedir config file in {}".format(e.basedir)
            print "Error on loading: {}".format(e.orig_e)
            print "Run mrl init in this directory first to make it a base directory."
        except InvalidExpIdException as e:
            print(e)
        except Exception as e:
            print "Unchecked exception"
            raise
    return
