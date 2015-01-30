outdir          = 'output'
singleExpFormat = '{expId:06d}'
batchExpFormat  = '{expId:06d}-{subExpId:03d}'
gitFailUntrackedDefault= 'no'
copyFiles       = ['conf.lua', 'models.lua']
batchTemplate   = 'conf.lua' # what file is expanded into template
launchScript    = 'run.q'
rstFile         = '.mrl.rst'
giturl          = 'git@github.com:tomsercu/lo.git'
files = {}
files['launchScript']=\
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
luajit go.lua -conf ../$EXPDIR/conf.lua -device 1 -noprogress -resume
"""
files['rst'] = \
"""desc:{{expId}} - {{timestamp}} - {{shortdescription}}
files:{{files}}
"""
