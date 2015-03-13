# Metarunlog
## Installation
-
```
git clone https://github.com/tomsercu/metarunlog
cd metarunlog
python setup.py install --user

```

## Get started 
+ basedir should typically be your git code directory. 
+ On mrl init, a .mrl.cfg file is created where the default config is copied into. Manually edit it. It will keep the id of the current experiment.

## Batch syntax
Metarunlog supports generating multiple config files automatically from a special config template, following jinja-syntax.
This is meant for automatic grid search.
The template provides a syntax to easily set hyperparameter values to do a grid search over.

Example code
```
mrl new -cp [other_batch] "description"
> ./output/000001
```
This generates a new directory and copies previous config files (specified in cfg.py or .mrl.cfg) over.

Now edit the config batch file, for example like this file conf.lua:
```
learning_rate = {% lr %}
wdecay = {% wdecay %}
other_value = 3
-- MRL:grid['lr'] = [0.01, 0.04, 0.1]
-- MRL:grid['wdecay'] = [0.1, 1.0, 10.0]
```

The template file should have the MRL (python) instructions in the last lines, 
starting with whatever comment-symbol your language uses, followed by a space and then either

+ MRL:grid['param'] = [values] 
+ MRL:params = [{'param1':1, 'param2':3}, ...].

After the template is set, use:
```
mrl batch [id]
```
This expands the template under id (default = last id) into subdirs, each containing one rendered config file.

## HPC support
The HPC support is fairly much tailored for my personal setup here at NYU but will probably be more broadly usable at any place that uses a cluster with qsub submission system.
It assumes some things like having a hpc connection set up in your .ssh/config so you can ssh/scp with just the hostname ('mercer' in cfg.py).
It also assumes qsub is available, some of the PBS flags might not make sense in another environment, but you can change the template in cfg.py and in your .mrl.cfg file.

## Custom jobs and scheduling
Metarunlog supports defining custom jobs. You typically want to use this for running the actual simulation, scoring, etc.

First of all, there are three concepts:
+ jobs (defined in cfg): dictionary of job names. Each job consists of a list of commands. For example, {"go": [checkout code at right commitId, execute experiment, score experiment], ...}
+ resources (defined in cfg): {'clustername': {'scheduler':'', 'host': [list of (host, device) tuples], 'copyFiles': True}, ... }
+ schedulers (localScheduler, sshScheduler, pbsScheduler): classes that reads in your computing resources, your job, and expId. It then manages the execution.

Jobs appear directly as commands in mrl -h. Running a job like this is the same as mrl scheduleLocal jobname.

Jobs are parametrized in config with
``` python
custom = {"commandName": [list of consecutive commands to be executed], ...}
```
with each command in the list of commands a dictionary (only "command" is required).
``` 
command = {
   "cwd": "will chdir here first",
   "command": "will be executed with subprocess, shell=True",
   "output": "will redirect output to this file inside the expDir (regardless of cwd)",
   "maxtime": time before killing the job, walltime for pbs.
}
```

## Analysis
(mrl analyze expId [anadir]) does the following on a finished batch experiment:
+ make anadir under expDir
+ generate html file with these sections: 
    * notes, parsed from .mrl.note in markdown format (start titles from level 3 onwards)
    * overview
    * a section per subexp
+ Generate the overview section as follows:
    * Use cfg.analysis\_overview = {'funcname': (xarg1, xarg2, etc), ... }
    * returnval is of the format: [(data, rtype, rheader or None), (...) ... ]
    * rtype is plot, table or text.
    * The functions are called as: getattr(analyze, funcname)(expDir, outdir, subExpIds, Dparams, \*xtrargs)
+ Generate per-subexp sections:
    * Use cfg.analysis\_subexp (the same way as above and same returnval format)
    * The functions are called as: getattr(analyze, funcname)(expDir, outdir, subExpIds, Dparams, \*xtrargs)
+ Make ipython / itorch notebook from template

## Todo
+ Parse notes in analysis

## Dependencies
+ sshpass: http://sourceforge.net/projects/sshpass/
+ jinja2: http://jinja.pocoo.org/
+ markdown for using analyze mode
