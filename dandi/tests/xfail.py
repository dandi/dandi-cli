# ex: set sts=4 ts=4 sw=4 noet:
# ## ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ##
#
#   See LICENSE file distributed along with the dandi-cli package for the
#   copyright and license terms.
#
# ## ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ##
"""Define reusable xfail markers for tests.

This module provides commonly used xfail markers that can be shared across
multiple test modules to avoid duplication.
"""
import sys

import pytest

# Reusable xfail markers

mark_xfail_windows_python313_posixsubprocess = pytest.mark.xfail(
    condition=sys.platform == "win32" and sys.version_info >= (3, 13),
    reason="Fails on Windows with Python 3.13 due to multiprocessing _posixsubprocess module error",
    strict=False,
    raises=AssertionError,
)
