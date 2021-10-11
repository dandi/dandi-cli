# ex: set sts=4 ts=4 sw=4 noet:
# ## ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ##
#
#   See LICENSE file distributed along with the dandi-cli package for the
#   copyright and license terms.
#
#   This file is borrowed from ReproMan, MIT license, Copyright 2016-2020
#   ReproMan developers.
#
# ## ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ##
"""Define `skipif` and `mark` namespaces for custom pytest skippers.

There are two main ways to skip in pytest:

* decorating a test function, such as::

        @pytest.mark.skip(sys.platform.startswith("win"), reason="on windows")
        def test_func():
            [...]

* skipping inline, such as::

        def test_func():
            if sys.platform.startswith("win"):
                pytest.skip("on Windows")
            [...]

This module provides a mechanism to register a reason and condition as both a
decorator and an inline function:

* Within this module, create a condition function that returns a tuple of the
  form (REASON, COND). REASON is a str that will be shown as the reason for
  the skip, and COND is a boolean indicating if the test should be skipped.

  For example::

    def windows():
        return "on windows", sys.platform.startswith("win")

* Then add the above function to CONDITION_FNS.

Doing that will make the skip condition available in two places:
`mark.skipif_NAME` and `skipif.NAME`. So, for the above example, there would
now be `mark.skipif_windows` and `skipif.windows`.
"""
import abc
import os
import shutil
import subprocess

import pytest

# from reproman.cmd import Runner
# from reproman.support.exceptions import CommandError
# from reproman.support.external_versions import external_versions
from ..utils import on_windows as _on_windows

# Condition functions
#
# To create a new condition, (1) add a condition function and (2) add that
# function to CONDITION_FNS.

# Left commented out for future references
# def no_apt_cache():
#     return ("apt-cache not available", not external_versions["cmd:apt-cache"])
#
#
# def no_aws_dependencies():
#     return "boto3 not installed", not external_versions["boto3"]
#
#
# def no_condor():
#     def is_running():
#         try:
#             Runner().run(["condor_status"])
#         except CommandError as exc:
#             return False
#         return True
#
#     return (
#         "condor not available",
#         not (external_versions["cmd:condor"] and is_running()),
#     )
#
#
# def no_datalad():
#     return ("datalad not available", not external_versions["datalad"])
#
#
# def no_docker_dependencies():
#     missing_deps = []
#     for dep in "docker", "dockerpty":
#         if dep not in external_versions:
#             missing_deps.append(dep)
#     msg = "missing dependencies: {}".format(", ".join(missing_deps))
#     return msg, missing_deps

# The following code is modified from the original ReproMan source:
# ### BEGIN MODIFIED CODE


def no_docker_commands():
    missing_cmds = []
    for cmd in ("docker", "docker-compose"):
        if shutil.which(cmd) is None:
            missing_cmds.append(cmd)
    msg = "missing Docker commands: {}".format(", ".join(missing_cmds))
    return msg, missing_cmds


def no_docker_engine():
    def is_engine_running():
        # from reproman.resource.docker_container import DockerContainer
        # return DockerContainer.is_engine_running()
        r = subprocess.run(["docker", "info"], stdout=subprocess.DEVNULL)
        return r.returncode == 0

    msg, missing_deps = no_docker_commands()
    if missing_deps:
        return msg, missing_deps
    return "docker engine not running", not is_engine_running()


def no_git():
    return "Git not installed", shutil.which("git") is None


# ### END MODIFIED CODE


def no_network():
    return ("no network settings", os.environ.get("DANDI_TESTS_NONETWORK"))


# def no_singularity():
#     return ("singularity not available", not external_versions["cmd:singularity"])


def no_ssh():
    if _on_windows:
        reason = "no ssh on windows"
    else:
        reason = "no ssh (DANDI_TESTS_SSH unset)"
    return (reason, _on_windows or not os.environ.get("DANDI_TESTS_SSH"))


# def no_svn():
#     return ("subversion not available", not external_versions["cmd:svn"])
#


def on_windows():
    return "on windows", _on_windows


CONDITION_FNS = [
    # no_apt_cache,
    # no_aws_dependencies,
    # no_condor,
    # no_datalad,
    # no_docker_dependencies,
    no_docker_commands,
    no_docker_engine,
    no_git,
    no_network,
    # no_singularity,
    no_ssh,
    # no_svn,
    on_windows,
]

# Entry points: skipif and mark


class NamespaceAttributeError(AttributeError):
    """Namespace-specific AttributeError.

    Raised by Namespace when it cannot find the specified condition function.
    Using a derived class allows us to distinguish an unknown condition
    function from a condition function that raises an AttributeError.
    """


class Namespace(object, metaclass=abc.ABCMeta):
    """Provide namespace skip conditions in CONDITION_FNS."""

    fns = {c.__name__: c for c in CONDITION_FNS}

    @abc.abstractmethod
    def attr_value(self, condition_func):
        """Given a condition function, return an attribute value."""

    def __getattr__(self, item):
        try:
            condfn = self.fns[item]
        except KeyError:
            raise NamespaceAttributeError(item) from None
        return self.attr_value(condfn)


class SkipIf(Namespace):
    """Namespace for inline variants of the condition functions.

    Each condition is available under an attribute with the same name as the
    condition function name.
    """

    def attr_value(self, condition_func):
        def fn():
            reason, cond = condition_func()
            if cond:
                pytest.skip(reason, allow_module_level=True)

        return fn


skipif = SkipIf()


class Mark(Namespace):
    """Namespace for mark variants of the condition functions.

    Each condition is available under an attribute "skipif_NAME", where NAME is
    the condition function name.
    """

    def attr_value(self, condition_func):
        reason, cond = condition_func()
        return pytest.mark.skipif(cond, reason=reason)

    def __getattr__(self, item):
        if item.startswith("skipif_"):
            try:
                return super(Mark, self).__getattr__(item[len("skipif_") :])
            except NamespaceAttributeError:
                # Fall back to the original item name so that the attribute
                # error message doesn't confusingly drop "skipif_".
                pass
        return super(Mark, self).__getattr__(item)


mark = Mark()
