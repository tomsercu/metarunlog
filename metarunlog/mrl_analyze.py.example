# Metarunlog, experiment management tool.
# Author: Tom Sercu
# Date: 2016-10-09
# Simple example functions to demonstrate working of the user-written mrl_analyze module.
# This module is meant to parse logs and produce plots / tables specific to the specific project.
# Place this file in the base directory along with .mrl.cfg
# The functions in this module have to be registered in your .mrl.cfg file

from os.path import join
import numpy as np
import matplotlib
try:
    matplotlib.use('agg')
except Exception as e:
    print(e) # using default backend which might need X server
print('backend', matplotlib.get_backend())
import matplotlib.pyplot as plt
import pandas as pd

def plotSinglePerf(subExpDir, outdir, Dparams, subExpId):
    logFile = join(subExpDir, 'output.log') # assumed plain file with one float per line
    logVals = np.loadtxt(logFile)
    pfn     = 'plot_{}.png'.format(subExpId)
    plt.plot(logVals)
    plt.savefig(join(outdir, pfn), bbox_inches='tight')
    plt.close()
    return [(pfn, 'plot', None)]

def bestPerf(expDir, outdir, subExpIds, Dparams):
    logFile = join(expDir, '{}', 'output.log') # assumed plain file with one float per line
    logVals = []
    res     = Dparams.copy()
    for subExpId in subExpIds:
        logVals = np.loadtxt(logFile.format(subExpId))
        res.ix[subExpId, 'max'] = logVals.max()
    return [(res, 'table', None)]
