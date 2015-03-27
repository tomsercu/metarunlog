#!/usr/bin/env python
# Metarunlog, experiment management tool.
# Author: Tom Sercu
# Date: 2015-03-26

import pandas as pd
from os.path import join
# Whetlab score function and score name
goScoreName = 'log likelihood'
def goScoreFunc(absloc):
    fn = join(absloc, 'logs/perf.csv')
    perfmat = pd.read_csv(fn)
    bestnll = perfmat['val_nll'].min()
    return (-bestnll)
