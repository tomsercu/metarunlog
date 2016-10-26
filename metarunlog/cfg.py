# Metarunlog, experiment management tool.
# Author: Tom Sercu
# Date: 2016-10-07
# Default configuration, values will be overwritten by .mrl.cfg in basedir.

name            = 'myproject'
outdir          = 'output'
singleExpFormat = '{expId:04d}'
subExpFormat    = '{subExpId:03d}'
gitFailUntrackedDefault= 'no'
copyFiles       = ['conf.lua']
confTemplFile   = 'conf.lua' # what file is expanded into template with makebatch()
giturl          = 'git@github.rtp.raleigh.ibm.com:multimodal/multilingconv.git'
analysis_overview = { # {funcname: ('extra_arg1', extrarg2, ), .. }
    'bestPerf': (),
}
analysis_subexp = {
    'plotSinglePerf': (),
}
analysis_webdir = '/u/tsercu/www'
hooks = {
    'after_new' : {},
    'after_makebatch' : {},
    'run'       : {},
    'score'     : {'epoch':None, 'langid':'swb', 'testset':'hub5','gammaN': 1, 'gammas': '{"0.8"}', 'acwtfrom': 1, 'acwtto': 3, 'subExps':'all'}
}
