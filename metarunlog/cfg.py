outdir          = 'output'
singleExpFormat = '{expId:04d}'
subExpFormat    = '{subExpId:03d}'
gitFailUntrackedDefault= 'no'
copyFiles       = ['conf.lua', 'modeldef.lua']
confTemplFile   = 'conf.lua' # what file is expanded into template when calling batch
#giturl          = 'git@github.com:tomsercu/lo.git'
giturl          = 'cims:~/lo'
hpcOutputData   = ['best_model.mat', 'last_model.mat'] # data, standard excluded from fetch
analysis_overview = { # {funcname: ('extra_arg1', extrarg2, ), .. }
    'bestPerf': (),
}
analysis_subexp = {
    'plotSinglePerf': (),
}
analysis_webdir = '/web/ts2387/lo/'
jobs = {
    "go": [
      "cd {{absloc}}",
      "(git clone {{giturl}} code || true)",
      "cd code",
      "git checkout {{gitHash}}",
      "luajit go.lua -conf {{absloc}}/conf.lua -device {{device|default('1')}} -noprogress"
    ],
    "attscore": [
      "mkdir -p {{absloc}}/ctm/{{acwt|default('0.09')}}",
      "cd attscore",
      "cd ~/attila/301/VLLP/buildDNN.SI.1/torchTest",
      "attila attscore/att.py -L {{relloc}} -w {{acwt|default('0.09')}}",
      "cd ~/attila/301/VLLP/scoring_",
      "attila score.py --langID=301.tune {{absloc}}/ctm/{{acwt|default('0.09')}}/"
    ] 
}
resources = {
    "local" : {
      "scheduler": "local"
    },
    "cims" : {
      "scheduler": "ssh",
      "hosts" : [["rose1", 2], ["rose2",2], ["rose4",1], ["rose4",2], ["rose9",2]],
      "copyFiles" : False,
      "askPass" : False
    },
    "hpc": {
      "scheduler": "pbs",
      "host" : "mercer",
      "copyFiles" : True,
      "askPass" : True,
      "qsubHeader" : ["#!/bin/bash",
                      "#PBS -l nodes=1:ppn=1:gpus=1:titan", 
                      "#PBS -l walltime=08:00:00", 
                      "#PBS -l mem=16GB", 
                      "module load cuda/6.5.12"]
    }
}
whetlab = {
    "jobName" : "go",
    "maxExperiments" : 1000,
    "expNamePrefix" : "lo_conv_",
    "token" : "fb2ff6fb-79e7-4b77-833a-64bcc8ad327e"
}
