import pandas as pd
import os
import subprocess
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
    # TODO add barplot
    return [(res, 'table', None)]

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
        return [(pfn1, 'plot', 'Error pct'), (pfn2, 'plot', 'nll loss')]
    else:
        return None

class HtmlFile:
    # TODO use jinja templating here
    def __init__(self):
        self.body = ""
        self.title = ""
    def addTitle(self, title):
        self.title = title
        self.body += "<h1>{}</h1>\n".format(title)
    def addHeader(self, hdr, level=1):
        self.body += "<h{level}>{hdr}</h{level}>\n".format(level=level+1, hdr=hdr)
    def addParagraph(self, txt):
        self.body += "<p>{}</p>\n".format(txt)
    def parseNote(self, notePath, v=True):
        try:
            self.body += subprocess.check_output(['markdown', notePath], stderr=subprocess.STDOUT) + '\n'
            if v: print "Parsed note {}".format(notePath)
        except subprocess.CalledProcessError as e:
            if 'No such file or directory' in e.output: 
                pass # no .mrl.note, no problem
                print "Didn't find note {}".format(join(expDir, '.mrl.note'))
            else:
                raise
            
    def render(self, fn, v=True):
        with open(fn, 'w') as fh:
            fh.write('<!DOCTYPE html>\n <html>\n <head>\n <title>{}</title>\n </head>\n\n'.format(self.title))
            fh.write('<body>{}</body>\n\n'.format(self.body))
            fh.write('</html>\n')
        if v: print "Wrote output to {}".format(fn)

    def addRetVal(self, retval):
        if not retval: #None or empty list
            return
        for (rdata, rtype, rheader) in retval:
            if rheader: 
                self.addHeader(rheader,4) # TODO nested header and menu?
            if rtype == 'table': 
                self.addTable(rdata)
            elif rtype == 'plot': 
                self.addPlot(rdata)
            elif rtype == 'text':
                self.addParagraph(text)
            else:
                raise Exception("Unknown rtype {}".format(rtype))
    def addPlot(self, plotfn):
        self.addParagraph('<img src="{}"></img>\n'.format(plotfn))
    def addTable(self, table): 
        self.addParagraph(table.to_html())
