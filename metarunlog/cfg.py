outdir          = 'output'
singleExpFormat = '{expId:06d}'
batchExpFormat  = '{expId:06d}-{subExpId:03d}'
gitFailUntrackedDefault= 'no'
copyFiles       = ['conf.lua', 'models.lua']
batchTemplFile  = 'conf.lua' # what file is expanded into template when calling batch
launchScriptFile= 'run{}.q'
qsubFile        = 'qsub.sh'
rstFile         = '.mrl.rst'
#giturl          = 'git@github.com:tomsercu/lo.git'
giturl          = 'cims:~/lo'
hpcServer       = 'mercer'  # needs hpc tunnel to be set up! Assumes entry in .ssh/config specifying port & user
hpcBasedir      = '~/lo'
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
rstTempl = \
"""desc:{{expId}} - {{timestamp}} - {{shortdescription}}
files:{{files}}
"""
