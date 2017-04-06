# Metarunlog (mrl)
This is a minimalistic experiment management tool, written in python.

## Goal and philosophy
+ Goal: manage your machine learning project experiments
+ Command line commands to create new experiment, expand a template to fill in changing hyperparameters, launch the experiment, parse the resulting output logs / csv and generate a webpage
+ Extend with python code specific to your project: parse log files, plot graphs with matplotlib or bokeh
+ Design principles:
    - Minimalistic, use sensible primitives
    - Experiments are based on folder structure
    - Work off git versioned codebase
    - Do not get in the way
    - Independent of any project and DL tool
+ What it does not do
    - Deal with schedulers
    - Keep a database across all experiments with best results
    - Automated hyperparam search
    - Leaderboard

## Hierarchy
+ Project: the project basedir is the root of the git repo containing this project's evolving codebase. It has a `.mrl.cfg` config file for this project subdirectory `outdir` for example `output` or `exps` where all the experiments live, which is not checked in to git.
+ Experiment: a directory under `outdir`, has the codebase checked out at specific commit, along with a template of the `config` or `run.sh` file, which defines most hyperparameters, some of them as `{{template_variables}}`. This is then expanded in:
+ subExperiment: a directory under `expDir`, has the config file of the experiment with all hyperparams filled out, using the codebase of parent experiment. All logfiles, stdout, images, checkpoints etc go here.

## Installation
Preferably in virtualenv or conda environment. Or use `python setup.py install --user`.

```
git clone https://github.com/tomsercu/metarunlog
cd metarunlog
python setup.py install

```

## New project
For a new project execute `mrl init outdir` from your project basedir.
This creates a `.mrl.cfg` json file, containing default config values. 
Manually edit it; specifically the `name`, `copyFiles` and `confTemplFile` fields.

## New experiment, config file template system
NOTE: `mrl -h` or `mrl subcommand -h` alwyas gives you info.

Metarunlog is designed around config file templates, which contain hyperparams of which some are template variables.
Config files could be either eg `cfg.py` which is then `import`ed by the codebase, or eg `run.sh` which contains the hyperparms as CL args.
The template provides a syntax to easily do a grid search over hyperparameters.

Example code
```
mrl new -cp [prev_expId] "My experiment description"
> ./outdir/expId
```

This generates a new directory in `outdir`, checks out your root dir at current commit, 
and copies over the config files from `prev_expId` as specified in `.mrl.cfg` field `copyFiles`.

Now edit the `confTemplFile`, for example like this file conf.lua:
```
local cfg = {
    learning_rate = {{lr}},
    wdecay    = {{wdecay}},
    momentum  = 3, -- doesn't change
    numLayers = 5
}
-- MRL:grid['lr'] = [0.01, 0.04, 0.1]
-- MRL:grid['wdecay'] = [0.1, 1.0, 10.0]
```

The template file should have the `mrl` instructions in the last lines, 
starting with whatever comment-symbol your language uses, followed by a space and then either

+ MRL:grid['param'] = [values] 
+ MRL:params = [{'param1':1, 'param2':3}, ...].

After the template is set, use:
```
mrl makebatch [expId]
```

This expands the conf template from experiment expId (default = last id) into subExperiments,
each containing one rendered config file.

## mrl analyze
Syntax:
`mrl analyze expId` 

+ generate html file with these sections: 
    * notes, parsed from `note_fn` in markdown format (start titles from level 3 onwards)
    * overview
    * a section per subExp
+ Generate the overview section as follows:
    * Use cfg.analysis\_overview = {'funcname': (xarg1, xarg2, etc), ... }
    * returnval is of the format: [(data, rtype, rheader or None), (...) ... ]
    * rtype is plot, table or text.
    * The functions are called as: getattr(analyze, funcname)(expDir, outdir, subExpIds, Dparams, \*xtrargs)
+ Generate per-subexp sections:
    * Use cfg.analysis\_subexp (the same way as above and same returnval format)
    * The functions are called as: getattr(analyze, funcname)(expDir, outdir, subExpIds, Dparams, \*xtrargs)
+ Make ipython / itorch notebook from template

## Hooks
You can define custom functionsin `mrl_hooks.py` and register them in `.mrl.cfg` field `hooks`.
`after_` and `before_` are magic prefixes which execute the hook before or after an existing function 
(for example, `after_new` or `after_makebatch`).

A hook should follow the syntax `def after_makebatch(self, args):` with `args` containing `expId`
and the other info contained in the `expId/.mrl` file.

## Dependencies
+ jinja2: http://jinja.pocoo.org/
+ for `mrl analyze`: markdown, bokeh, pandas
