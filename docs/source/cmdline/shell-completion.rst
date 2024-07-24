:program:`lincbrain shell-completion`
=====================================

::

    lincbrain [<global options>] shell-completion [<options>]

Emit a shell script for enabling command completion.

The output of this command should be "sourced" by bash or zsh to enable command
completion.

Example::

    $ source <(lincbrain shell-completion)
    $ lincbrain --<PRESS TAB to display available option>

Options
-------

.. option:: -s, --shell [bash|zsh|fish|auto]

    The shell for which to generate completion code; ``auto`` (default)
    attempts autodetection
