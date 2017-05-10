# Metarunlog, experiment management tool.
# Author: Tom Sercu
# Date: 2016-10-09
# Defines HtmlFile and helper functions to build up the index.html from mrl_analyze functions output.

import os
import subprocess
from os.path import join
import numpy as np
import markdown
import bokeh
from bokeh.embed import components

bokehCdn = """<script src="http://cdn.pydata.org/bokeh/release/bokeh-{0}.min.js"></script>
<script src="http://cdn.pydata.org/bokeh/release/bokeh-widgets-{0}.min.js"></script>
<link href="http://cdn.pydata.org/bokeh/release/bokeh-{0}.min.css" rel="stylesheet" type="text/css">
<link href="http://cdn.pydata.org/bokeh/release/bokeh-widgets-{0}.min.css" rel="stylesheet" type="text/css">"""\
        .format(bokeh.__version__)

class HtmlFile:
    # TODO use jinja templating here
    def __init__(self):
        self.body = ""
        self.title = ""
        self.bokehScripts = ""
    def addTitle(self, title):
        self.title = title
        self.body += "<h1>{}</h1>\n".format(title)
    def addHeader(self, hdr, level=1, anchor=None):
        if anchor:
            hdr = '<a name="{}">{}</a>'.format(anchor, hdr)
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
            head = '<title>{}</title>\n{}\n{}\n'.format(
                    self.title, bokehCdn if self.bokehScripts else '', self.bokehScripts)
            fh.write('<!DOCTYPE html>\n <html>\n<head>\n{}\n</head>\n\n'.format(head))
            fh.write('<body>{}</body>\n\n'.format(self.body))
            fh.write('</html>\n')
        if v: print "Wrote output to {}".format(fn)

    def addRetVal(self, retval):
        if not retval: #None or empty list
            return
        for (rdata, rtype, rheader) in retval:
            if rheader: 
                self.addHeader(rheader,3) # TODO nested header and menu?
            if rtype in ['table', 'plot', 'text', 'mp4', 'bokeh', 'plotlinkbokeh', 'html']:
                addFunc = getattr(self, 'add' + rtype.capitalize())
                addFunc(rdata)
            else:
                raise Exception("Unknown rtype {}".format(rtype))

    def addHtml(self, htmlString):
        self.body += htmlString
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
    def addBokeh(self, bokehPlot):
        script, div = components(bokehPlot)
        self.bokehScripts += script + '\n'
        self.body += div + '\n'
    def addPlotlinkbokeh(self, rdata):
        plotfn, bokehfn = rdata
        self.addParagraph('<a href="{}"><img src="{}"></img></a>\n'.format(
            bokehfn, plotfn))
