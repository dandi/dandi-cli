import os
from os.path import basename, normcase, splitext

import click
from packaging.version import Version

SHELLS = ["bash", "zsh", "fish"]


@click.command("shell-completion")
@click.option(
    "-s",
    "--shell",
    type=click.Choice(["auto"] + SHELLS),
    default="auto",
    show_default=True,
    help="The shell for which to generate completion code; `auto` attempts autodetection",
)
def shell_completion(shell):
    """
    Emit shell script for enabling command completion.

    The output of this command should be "sourced" by bash or zsh to enable
    command completion.

    Example:

    \b
        $ source <(dandi shell-completion)
        $ dandi --<PRESS TAB to display available option>
    """
    if shell == "auto":
        try:
            shell = basename(os.environ["SHELL"])
        except KeyError:
            raise click.UsageError(
                "Could not determine running shell: SHELL environment variable not set"
            )
        shell = normcase(shell)
        stem, ext = splitext(shell)
        if ext in (".com", ".exe", ".bat"):
            shell = stem
        if shell not in SHELLS:
            raise click.UsageError(f"Unsupported/unrecognized shell {shell!r}")
    if Version(click.__version__) < Version("8.0.0"):
        varfmt = "source_{shell}"
    else:
        varfmt = "{shell}_source"
    os.environ["_DANDI_COMPLETE"] = varfmt.format(shell=shell)

    from .command import main

    main.main(args=[])
