# Metarunlog, experiment management tool.
# Author: Tom Sercu

import datetime

def nowstring(sec=True, ms= False):
    tstr = datetime.datetime.now().isoformat()
    if not ms:
        tstr = tstr.split('.')[0]
    if not sec:
        tstr = tstr.rsplit(':',1)[0]
    return tstr

def sshify(cmd, sshHost, sshPass, vfh=None):
    cleancmd = ''
    if sshHost:
        cmd = 'ssh {} "{}"'.format(sshHost, cmd)
    if sshPass:
        cleancmd = "sshpass -p '{}' {}".format('***', cmd)
        cmd = "sshpass -p '{}' {}".format(sshPass, cmd)
    # printing
    if not cleancmd: cleancmd = cmd
    if vfh: vfh.write(cleancmd + '\n')
    return cmd
