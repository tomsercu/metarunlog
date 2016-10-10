# Metarunlog, experiment management tool.
# Author: Tom Sercu
# Date: 2016-10-07
from jinja2 import Template
from collections import OrderedDict
import itertools

class ConfParser:
    """
    ConfParser class will take a template experiment config file, 
    which ends with MRL:grid[] or MRL:params instructions and allow
    easy expansion into real experiment config files.
    It is initialized with experiment config template (list of lines)
    including the last lines determining the values,
    and generates self.output as a list of strings (to be written to file).
    """
    def __init__(self, templatefile):
        try:
            with open(templatefile) as fh:
                self.template = fh.readlines()
        except jinja2.exceptions.TemplateSyntaxError as e:
            err = "TemplateSyntaxError in your {} template file: \n {}".format(cfg.confTemplFile, str(e))
            raise ConfParserException(err)
        self.jtmpl = Template("".join(self.template))
        grid = OrderedDict()
        params = [{}]
        # iterate over last lines and parse them to collect grid parameters.
        # correct formatting of mrl instructions:
        # [something] MRL:grid['key'] = [vallist]
        # where [something] is comment symbol. The space after it is essential.
        for line in self.template[::-1]:
            if not line.strip(): continue
            line = line.split(None, 1)[-1].split(":",1) #discard comment symbol
            if line[0] != 'MRL': break
            exec(line[1]) #add to grid / params
        # construct output params list
        keys = grid.keys()
        vals = list(itertools.product(*[grid[k] for k in keys]))
        self.params = [dict(zip(keys, v)) for v in vals]
        self.params = [dict(d1.items() + d2.items()) for d1,d2 in itertools.product(params, self.params)]
        self.output = []
        for i, param in enumerate(self.params):
            self.output.append((i+1, param, self.renderFromParams(param)))

    def renderFromParams(self, params):
        """ Render the configuration file template from given parameters. """
        return self.jtmpl.render(**params)
