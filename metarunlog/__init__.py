#!/usr/bin/env python
# Metarunlog, experiment management tool.
# Author: Tom Sercu
# Date: 2015-01-23

import metarunlog.cfg as cfg
import os
import sys
from os import listdir
from os.path import isdir, isfile, join

def checkValidExp(name):
    if len(name) != cfg.singleExpFormat.format(exp=0): return False
    try:
        int(name)
    except:
        return False

class MetaRunLog:
    def __init__(self):
        self.basedir = os.getcwd()
        self.outdir  = join(self.basedir, cfg.outdir)
        self.expList = sorted([int(x) for x in listdir(self.outdir) if checkValidExp(x)])

    def new(self):
        pass

def main(args):
    if not args:
        print "Usage: mrl [mode] [arguments]. mrl help for more info"
        return
    mode = args[0]
    if mode == "help":
        print "Todo"
