import logging
import os

from . import _version

__version__ = _version.get_versions()["version"]


from .due import Doi, due

due.cite(
    Doi("10.5281/zenodo.3692138"),  # lgtm [py/procedure-return-value-used]
    cite_module=True,  # highly specialized -- if imported, means used.
    description="Client to interact with DANDI Archive",
    path="dandi-cli",
    version=__version__,  # since yoh hijacked dandi for module but is not brave enough
    # to claim it to be dandi as the whole
)


#
# Basic logger configuration
#


def get_logger(name=None):
    """Return a logger to use"""
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


lgr = get_logger()
set_logger_level(lgr, os.environ.get("DANDI_LOG_LEVEL", logging.INFO))
