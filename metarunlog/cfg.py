outdir          = 'output'
singleExpFormat = '{expId:06d}'
batchExpFormat  = '{subExpId:03d}'
gitFailUntrackedDefault= 'no'
copyFiles       = ['conf.lua', 'modeldef.lua']
batchTemplFile  = 'conf.lua' # what file is expanded into template when calling batch
launchScriptFile= 'run{}.q'
qsubFile        = 'qsub.sh'
#giturl          = 'git@github.com:tomsercu/lo.git'
giturl          = 'cims:~/lo'
hpcServer       = 'mercer'  # needs hpc tunnel to be set up! Assumes entry in .ssh/config specifying port & user
hpcBasedir      = '~/lo'
#hpcOutputLogs   = 'logs/*'
hpcOutputData   = ['best_model.mat', 'last_model.mat'] # data, standard excluded from fetch
launchScriptTempl=\
"""#!/bin/bash
#PBS -l nodes=1:ppn=1:gpus=1:titan
#PBS -l walltime=10:00:00
#PBS -l mem=16GB
module load cuda/6.5.12
BASE={{basedir}} #absolute
EXPDIR={{expDir}} #relative
cd ${BASE}/${EXPDIR}
git clone {{giturl}} code
cd code
git checkout {{gitHash}}
luajit go.lua -conf ../conf.lua -device 1 -noprogress -resume
"""
analysis_overview = { # {funcname: ('extra_arg1', extrarg2, ), .. }
    'bestPerf': (),
}
analysis_subexp = {
    'plotSinglePerf': (),
}
analysis_webdir = '/web/ts2387/lo/'
jobs = {
    "run": [
      { "command": "luajit go.lua -conf {{absloc}} -device {{device}}" }
    ],
    "runSilent": [
      { "command": "luajit go.lua -conf {{absloc}} -device {{device|default('1')}} -noprogress",
        "output": "go.log" }
    ],
}
resources = {
    "local" : {
      "scheduler": "local"
    }
}
