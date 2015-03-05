import pandas as pd
import os
import subprocess
from os.path import join
import matplotlib; matplotlib.use('agg')
import matplotlib.pyplot as plt
import markdown

def bestPerf(expDir, outdir, subExpIds, Dparams, barxlim=[0.5, 1.0]):
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
    # drop columns that have only one value
    summary = "#### Parameters that didn't vary:\n"
    for c in res.columns:
        colvals = res[c].unique()
        if len(colvals) == 1:
            summary += '+ {}\t{}\n'.format(c, colvals[0])
            del res[c]
    # add the best performance as columns to res dataframe
    bestepochs = [m['val_err'].idxmin() for m in perfmats]
    bestrows = [m.loc[bepoch] for m,bepoch in zip(perfmats, bestepochs)]
    res['best_epoch'] = ['{} / {}'.format(be, te) for be, te in zip(bestepochs, [len(m) for m in perfmats])]
    res['val_err'] = [brow['val_err'] for brow in bestrows]
    res['train_err'] = [brow['train_err'] for brow in bestrows]
    res['val_nll'] = [brow['val_nll'] for brow in bestrows]
    res['train_nll'] = [brow['train_nll'] for brow in bestrows]
    # make barplot
    pfn = 'ov_bestPerf_bars.png'
    res[['val_err', 'train_err']].plot(kind='barh')
    plt.legend(loc=2)
    plt.xlim(*barxlim)
    plt.savefig(join(outdir, pfn))
    plt.close()
    return [(summary, 'text', None), (res, 'table', None), (pfn, 'plot', None)]

def plotSinglePerf(expDir, outdir, Dparams=None, runId='def'):
    print("plotSinglePerf: plot train/val err and nll - {}".format(runId))
    fn = join(expDir, 'logs/perf.csv')
    try:
        perfmat = pd.read_csv(fn)
    except:
        return None
    else:
        pfn1 = 'plotSinglePerf_{}_err.png'.format(runId)
        perfmat[['train_err', 'val_err']].plot()
        plt.savefig(join(outdir, pfn1))
        plt.close()
        pfn2 = 'plotSinglePerf_{}_nll.png'.format(runId)
        perfmat[['train_nll', 'val_nll']].plot()
        plt.savefig(join(outdir, pfn2))
        plt.close()
        if Dparams:
            # print my params (indented for markdown code)
            myparams = '\n'.join('    '+x for x in str(Dparams).split('\n'))
            return [(myparams, 'text', 'Params'), (pfn1, 'plot', 'Error pct'), (pfn2, 'plot', 'nll loss')]
        else:
            return [(pfn1, 'plot', 'Error pct'), (pfn2, 'plot', 'nll loss')]

class HtmlFile:
    # TODO use jinja templating here
    def __init__(self):
        self.body = ""
        self.title = ""
    def addTitle(self, title):
        self.title = title
        self.body += "<h1>{}</h1>\n".format(title)
    def addHeader(self, hdr, level=1):
        self.body += "<h{level}>{hdr}</h{level}>\n".format(level=level, hdr=hdr)
    def addParagraph(self, txt):
        self.body += "<p>{}</p>\n".format(txt)
    def parseNote(self, notePath, v=True):
        try:
            with open(notePath) as fh:
                self.body += markdown.markdown(fh.read())+'\n'
            if v: print "Parsed note {}".format(notePath)
        except IOError as e:
            print "Didn't find note {}".format(notePath)

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
                self.addHeader(rheader,3) # TODO nested header and menu?
            if rtype == 'table': 
                self.addTable(rdata)
            elif rtype == 'plot': 
                self.addPlot(rdata)
            elif rtype == 'text':
                self.addText(rdata)
            else:
                raise Exception("Unknown rtype {}".format(rtype))

    def addPlot(self, plotfn):
        self.addParagraph('<img src="{}"></img>\n'.format(plotfn))
    def addTable(self, table): 
        self.addParagraph(table.to_html())
    def addText(self, text):
        self.body += markdown.markdown(text)
