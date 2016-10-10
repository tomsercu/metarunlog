# Metarunlog, experiment management tool.
# Author: Tom Sercu
# Date: 2016-10-07
class InvalidOutDirException(Exception):
    pass
class NoBasedirConfig(Exception):
    def __init__(self, basedir, e):
        self.basedir = basedir
        self.orig_e = e
    def __str__(self):
        return "NoBasedirConfig in {} : {}".format(self.basedir, self.orig_e)
class NoCleanStateException(Exception):
    pass
class InvalidExpIdException(Exception):
    pass
class BatchException(Exception):
    pass
class ConfParserException(Exception):
    pass
