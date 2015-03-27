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

def _decode_list(data):
    rv = []
    for item in data:
        if isinstance(item, unicode):
            item = item.encode('utf-8')
        elif isinstance(item, list):
            item = _decode_list(item)
        elif isinstance(item, dict):
            item = _decode_dict(item)
        rv.append(item)
    return rv

def _decode_dict(data):
    rv = {}
    for key, value in data.iteritems():
        if isinstance(key, unicode):
            key = key.encode('utf-8')
        if isinstance(value, unicode):
            value = value.encode('utf-8')
        elif isinstance(value, list):
            value = _decode_list(value)
        elif isinstance(value, dict):
            value = _decode_dict(value)
        rv[key] = value
    return rv
