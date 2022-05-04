#!/usr/bin/env python
# emacs: -*- mode: python-mode; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:
# ## ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ##
#
#   See LICENSE file distributed along with the dandi-cli package for the
#   copyright and license terms.
#
# ## ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ##
"""Build helper."""

import os.path
import sys

from setuptools import setup

if sys.version_info < (3,):
    raise RuntimeError(
        "dandi-cli's setup.py requires python 3 or later. "
        "You are using %s" % sys.version
    )

# This is needed for versioneer to be importable when building with PEP 517.
# See <https://github.com/warner/python-versioneer/issues/193> and links
# therein for more information.
sys.path.insert(0, os.path.dirname(__file__))

try:
    import versioneer

    setup_kw = {
        "version": versioneer.get_version(),
        "cmdclass": versioneer.get_cmdclass(),
    }
except ImportError:
    # see https://github.com/warner/python-versioneer/issues/192
    print("WARNING: failed to import versioneer, falling back to no version for now")
    setup_kw = {}

if __name__ == "__main__":
    setup(name="dandi", **setup_kw)
