import pandas as pd
import os
from os.path import join
import matplotlib; matplotlib.use('agg')
import matplotlib.pyplot as plt

def bestPerf(expDir, outdir, subExpIds, Dparams):
    print("overview - bestPerf: table and plot of best errors, {} subExpIds".format(len(subExpIds)))
    perffns = [join(expDir, subExpId, 'logs/perf.csv') for subExpId in subExpIds]
    perfmats = []
    for fn in perffns:
        try:
            perfmats.append(pd.read_csv(fn))
        except:
            perfmats.append(None)
    perfmats = pd.Series(perfmats, index=subExpIds)
    drop = perfmats.isnull()
    res = Dparams[~perfmats.isnull()]
    perfmats = perfmats[~perfmats.isnull()]
    # TODO drop columns that have only one value
    #bestidx = 
    bestrows = [m.loc[m['val_err'].idxmin()] for m in perfmats]
    res['val_err'] = [brow['val_err'] for brow in bestrows]
    res['train_err'] = [brow['train_err'] for brow in bestrows]
    res['val_nll'] = [brow['val_nll'] for brow in bestrows]
    res['train_nll'] = [brow['train_nll'] for brow in bestrows]
    return res 

def plotSinglePerf(expDir, outdir, Dparams, runId):
    print("subexp - plotSinglePerf: plot train/val err and nll - {}".format(runId))
    fn = join(expDir, 'logs/perf.csv')
    if os.path.exists(fn):
        perfmat = pd.read_csv(fn)
        pfn1 = 'plotSinglePerf_{}_err.png'.format(runId)
        perfmat[['train_err', 'val_err']].plot()
        plt.savefig(join(outdir, pfn1))
        plt.close()
        pfn2 = 'plotSinglePerf_{}_nll.png'.format(runId)
        perfmat[['train_nll', 'val_nll']].plot()
        plt.savefig(join(outdir, pfn2))
        plt.close()
        return [pfn1, pfn2]
    else:
        return None
