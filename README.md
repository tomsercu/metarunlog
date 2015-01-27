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

Todo
-
+ Current experiment should not be a global (basedir) property, rather a per-shell or per-client one.

