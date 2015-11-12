import os
import subprocess
from os.path import join
import numpy as np
import markdown
try:
    # Make myAnalyze.py file in your mrl basedir and register the functions in your basedir .mrl.cfg file
    from myAnalyze import *
except Exception as e:
    print("Could not load local myAnalyze module: {}".format(str(e)))

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
            elif rtype == 'mp4':
                self.addMp4(rdata)
            else:
                raise Exception("Unknown rtype {}".format(rtype))

    def addPlot(self, plotfn):
        self.addParagraph('<img src="{}"></img>\n'.format(plotfn))
    def addTable(self, table): 
        self.addParagraph(table.to_html(escape=False))
    def addText(self, text):
        self.body += markdown.markdown(text)
    def addMp4(self, videofn):
        self.body += '<div>\n<video preload="none" controls>\n'
        self.body += '<source src="{}" type="video/mp4; codecs="avc1.42E01E, mp4a.40.2"">'.format(videofn)
        self.body += '</video>\n</div>\n'
