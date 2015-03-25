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
