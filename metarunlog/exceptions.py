class InvalidOutDirException(Exception):
    pass
class NoCleanStateException(Exception):
    pass
class NoBasedirConfig(Exception):
    def __init__(self, basedir, e):
        self.basedir = basedir
        self.orig_e = e
    def __str__(self):
        return "NoBasedirConfig in {} : {}".format(self.basedir, self.orig_e)
class InvalidExpIdException(Exception):
    pass
class BatchException(Exception):
    pass
class ConfParserException(Exception):
    pass
class HpcException(Exception):
    pass
class NoSuchJobException(Exception):
    pass
class SchedulerException(Exception):
    pass
class JobException(Exception):
    pass
