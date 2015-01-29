Metarunlog
===
Installation
-
```
git clone https://github.com/tomsercu/metarunlog
cd metarunlog
python setup.py install --user

```

Notes
-

+ basedir should typically be your git code directory. 
+ On mrl init, a .mrl.cfg file is created where the default config is copied into. Manually edit it. It will keep the id of the current experiment.

Batch syntax
-
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

Todo
-
+ Current experiment should not be a global (basedir) property, rather a per-shell or per-client one. Or, maybe it doesn't matter if we're always working with screen/manual runs OR trainSlave and trainMaster.
+ Name new folders w short description: "000001-blab_bla"


