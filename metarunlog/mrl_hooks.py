# Metarunlog, experiment management tool.
# Author: Tom Sercu
# Date: 2016-10-10
# Simple example hooks to demonstrate working of the user-written mrl_hooks module.
# This module allows for project-specific extensions of the mrl commands.
# Function names are important: "before_" and "after_" prefix will hook to existing command,
# while without prefix will become a new command.
# The hooks wil be registered on mrlState so will have access to the mrlState in self.

import cfg      # includes modifications from __init__
import os, subprocess, time
from os.path import join
from jinja2 import Template

def after_new(self, args):
    expId, expDir, expConfig = self._loadExp('last') # newly defined exp
    # clone code
    cmd = 'cd {}; git clone {} code; cd code; git checkout {}'.format( expDir, cfg.giturl, expConfig['gitHash'])
    print(cmd)
    subprocess.call(cmd, shell=True)

def after_makebatch(self, args):
    expId, expDir, expConfig = self._loadExp(args.expId)
    subExpList               = self._getSubExperiments(expDir)
    # write launch.sh file
    launchFile = \
"""proj=resnet{}
for subexp in {}; do
    cmd=". ~/.bashrc; sysinfo; cd code; luajit go.lua -conf ../${{subexp}}/conf.lua -resume -nGPU 4"
    echo $cmd
    jbsub -cores 2+4 -mem 40g -queue p8 -out ${{subexp}}/run.stdout -proj ${{proj}} -name ${{proj}}_${{subexp}} ${{cmd}}
done
    """
    launchFile = launchFile.format(expId, ' '.join(subExpList))
    fn = join(expDir, 'launch.sh')
    with open(fn,'w') as fh:
        fh.write(launchFile)
    subprocess.call('chmod u+x {}'.format(fn), shell=True)

def run(self, args):
    expId, expDir, expConfig = self._loadExp(args.expId)
    # submit jobs
    subprocess.call('cd {}; ./launch.sh'.format(expDir), shell=True)

def score(self, args):
    expId, expDir, expConfig = self._loadExp(args.expId)
    subExpList               = self._getSubExperiments(expDir)
    # other vals for spj template
    args = vars(args) # convert to dict
    epoch   = args.get('epoch',    300) # extract w defaults so that the xargs in .mrl.cfg can be added & deleted
    epochnr = int(epoch)
    langid  = args.get('langid',  'swb')
    testset = args.get('testset', 'hub5')
    gammas  = args.get('gammas',  '{"0.8"}')
    gammaN  = args.get('gammaN',   1)
    acwtfrom= args.get('acwtfrom', 1)
    acwtto  = args.get('acwtto',   3)
    # clone attscore
    if not os.path.exists(join(expDir, 'attscore')):
        subprocess.call('cd {}; git clone {} attscore'.format(
            expDir, 'git@github.rtp.raleigh.ibm.com:tsercu-us/attscore.git'), shell=True)
    # write the spj files from template
    templatefn = join(expDir, 'attscore/test.spj.template')
    template   = Template(open(templatefn).read() + '\n')
    templargs = {'langid':langid, 'mdl':'epoch%d'%epochnr, 'testset':testset, 'gammas':gammas, 'gammaN':gammaN, 'acwtfrom':acwtfrom, 'acwtto': acwtto}
    spjscript = template.render(**templargs)
    # for each subexp, write out test-spj script and run it
    for sj, subexpid in enumerate(subExpList):
        mdl_chkp = join(expDir, subexpid, 'epoch{}_{}.mdl.mat'.format(epochnr, langid))
        if not os.path.exists(mdl_chkp):
            print('SKIP {} subexpid {}, checkpoint {} doesnt exist'.format(sj, subexpid, mdl_chkp))
            continue
        print('{}  epoch{}'.format(subexpid, epochnr))
        # WRITE SCRIPT
        spjfn = 'test_{}_{}_{}_{}.spj'.format(expId, subexpid, epochnr, testset)
        if os.path.exists(join(expDir, subexpid, spjfn)):
            print('Skipping {} subexpid {}, spj-file {} already exists.'.format(sj,subexpid, spjfn))
            continue
        open(join(expDir, subexpid, spjfn), 'w').write(spjscript)
        # SPJB START
        #cmd = 'cd ' + base + subexpid + '; spjb ' + spjfn + ' start'
        cmd = 'cd {}/{}; spjb {} start'.format(expDir, subexpid, spjfn)
        print(cmd)
        time.sleep(0.3)
        subprocess.call(cmd, shell=True)
