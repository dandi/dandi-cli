:program:`dandi validate-bids`
==============================

::

    dandi [<global options>] validate-bids [<options>] [<path> ...]

Validate BIDS paths.

.. note::

    This command is deprecated: :ref:`dandi validate <dandi_validate>`
    validates BIDS datasets along with everything else and should be used
    instead.  ``dandi validate-bids`` now merely invokes it with the given
    paths and :option:`--grouping` (after emitting a deprecation warning).

Options
-------

.. option:: -g, --grouping [none|path]

    How to group the reported results  [default: ``none``]

.. option:: --report-path <path>

    Accepted for backwards compatibility but ignored

.. option:: -r, --report

    Accepted for backwards compatibility but ignored

.. option:: --schema VERSION

    Accepted for backwards compatibility but ignored
