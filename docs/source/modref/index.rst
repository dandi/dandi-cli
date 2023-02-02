.. -*- mode: rst -*-
.. vi: set ft=rst sts=4 ts=4 sw=4 et tw=79:

.. currentmodule:: dandi

.. _chap_modref:

**********
Python API
**********

High-level user interfaces
==========================

Such interfaces mirror :ref:`Command-Line Interfaces <chap_cmdline>`.

.. autosummary::
   :toctree: generated

   delete
   download
   move
   organize
   upload
   validate

Mid-level user interfaces
==========================

These interfaces provide object-oriented interfaces to manipulate Dandisets and assets in the
archive.

.. toctree::

   dandiarchive

Low-level user interfaces
=========================

Low level interfaces to e.g. interact with archive REST API interfaces and files directly.

.. toctree::

   dandiapi
   files
   misctypes

Support functionality
=====================

.. toctree::

   consts
   utils
   support.digests

Test infrastructure
===================

.. autosummary::
   :toctree: generated

   tests.fixtures
   tests.skip

..
    Command line interface infrastructure
    =====================================

    .. autosummary::
       :toctree: generated
