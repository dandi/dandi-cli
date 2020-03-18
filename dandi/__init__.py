import logging
import os
from . import _version

__version__ = _version.get_versions()["version"]


#
# Basic logger configuration
#


def get_logger(name=None):
    """Return a logger to use
    """
    return logging.getLogger("dandi" + (".%s" % name if name else ""))


def set_logger_level(lgr, level):
    if isinstance(level, int):
        pass
    elif level.isnumeric():
        level = int(level)
    elif level.isalpha():
        level = getattr(logging, level)
    else:
        lgr.warning("Do not know how to treat loglevel %s" % level)
        return
    lgr.setLevel(level)


_DEFAULT_LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

lgr = get_logger()
# Basic settings for output, for now just basic
set_logger_level(lgr, os.environ.get("DANDI_LOG_LEVEL", logging.INFO))
FORMAT = "%(asctime)-15s [%(levelname)8s] %(message)s"
logging.basicConfig(format=FORMAT)

# Run telemetry on import for interactive sessions, such as IPython, Jupyter
# notebooks, Python REPL
import __main__

if not hasattr(__main__, "__file__"):
    import etelemetry

    etelemetry.check_available_version("dandi/dandi-cli", __version__, lgr=lgr)
