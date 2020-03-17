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


def check_latest_version(raise_exception=False):
    """
    Check for the latest version of the library.
    Parameters
    ----------
    raise_exception: :obj:`bool`
        Raise a RuntimeError if a bad version is being used
    """
    import etelemetry
    from pkg_resources import parse_version

    logger = lgr

    INIT_MSG = "Running {packname} version {version} (latest: {latest})".format

    latest = {"version": "Unknown", "bad_versions": []}
    result = None
    try:
        result = etelemetry.get_project("dandi/dandi-cli")
    except Exception as e:
        logger.warning("Could not check for version updates: \n%s", e)
    finally:
        if result:
            latest.update(**result)
            if parse_version(__version__) != parse_version(latest["version"]):
                logger.info(
                    INIT_MSG(
                        packname="dandi", version=__version__, latest=latest["version"]
                    )
                )
            if latest["bad_versions"] and any(
                [
                    parse_version(__version__) == parse_version(ver)
                    for ver in latest["bad_versions"]
                ]
            ):
                message = (
                    "You are using a version of dandi cli with a critical "
                    "bug. Please use a different version."
                )
                if raise_exception:
                    raise RuntimeError(message)
                else:
                    logger.critical(message)
    return latest


# Run telemetry on import for interactive sessions, such as IPython, Jupyter notebooks, Python REPL
import __main__

if not hasattr(__main__, "__file__"):
    check_latest_version()
