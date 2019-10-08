import logging

from . import _version

__version__ = _version.get_versions()["version"]


#
# Basic logger configuration
#


def get_logger(name=None):
    """Return a logger to use
    """
    return logging.getLogger("dandi" + (".%s" % name if name else ""))


_DEFAULT_LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

lgr = get_logger()
# Basic settings for output, for now just basic
lgr.setLevel(logging.INFO)
FORMAT = "%(asctime)-15s [%(levelname)8s] %(message)s"
logging.basicConfig(format=FORMAT)
