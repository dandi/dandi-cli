:program:`lincbrain`
====================

::

    lincbrain [<global options>] <subcommand> [<arguments>]

A command-line client for interacting with the `LINC Data Platform
<http://lincbrain.org>`_.

Global Options
--------------

.. option:: -l <level>, --log-level <level>

    Set the `logging level`_ to the given value; default: ``INFO``.  The level
    can be given as a case-insensitive level name or as a numeric value.

    .. _logging level: https://docs.python.org/3/library/logging.html
                       #logging-levels

.. option:: --pdb

    Handle errors by opening `pdb (the Python Debugger)
    <https://docs.python.org/3/library/pdb.html>`_
