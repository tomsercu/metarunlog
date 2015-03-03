outdir          = 'output'
singleExpFormat = '{expId:06d}'
batchExpFormat  = '{subExpId:03d}'
gitFailUntrackedDefault= 'no'
copyFiles       = ['conf.lua', 'modeldef.lua']
batchTemplFile  = 'conf.lua' # what file is expanded into template when calling batch
launchScriptFile= 'run{}.q'
qsubFile        = 'qsub.sh'
rstFile         = '.mrl.rst'
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
analysis_overview = { # {funcname: ('extra_arg1', ...),  .. }
    'bestPerf': 'table',
}
analysis_subexp = {
    'plotSinglePerf': 'plot', # plot
}
analysis_webdir = '/web/ts2387/lo/'
custom = {
    "score": [
      {
        "command": "mkdir -p ./output/{{relloc}}/ctm/{{acwt}}"
      },
      {
        "command": "attila test.py -L {{relloc}} -w {{acwt}}",
        "cwd": "~/attila/301/VLLP/buildDNN.SI.1/torchTest",
        "output": "ctm/{{acwt}}/attila_decode.log"
      },
      {
        "command": "attila score.py --langID=301.tune {{absloc}}/ctm/{{acwt}}/",
        "cwd": "~/attila/301/VLLP/scoring_",
        "output": "ctm/{{acwt}}/attila_score.log"
      }
    ],
    "scoreSome": [
      {
        "command": "mkdir -p ./output/{{relloc}}/ctm{{uttlim}}/{{acwt}}"
      },
      {
        "command": "attila test.py -L {{relloc}} -w {{acwt}} -M {{uttlim}}",
        "cwd": "~/attila/301/VLLP/buildDNN.SI.1/torchTest",
        "output": "ctm{{uttlim}}/{{acwt}}/attila_decode.log"
      },
      {
        "command": "attila score.py --langID=301.tune {{absloc}}/ctm{{uttlim}}/{{acwt}}/",
        "cwd": "~/attila/301/VLLP/scoring_",
        "output": "ctm{{uttlim}}/{{acwt}}/attila_score.log"
      }
    ]
}
