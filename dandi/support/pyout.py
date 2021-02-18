"""pyout support helpers
"""
from collections import Counter
import datetime
import logging
import sys
import time

import humanize
import pyout

from ..consts import metadata_dandiset_fields, metadata_nwb_fields
from .. import get_logger

lgr = get_logger()


def fancy_bool(v):
    # TODO: move such supports into pyout since we should not
    # investigate here either terminal/output supports ANSI
    # should be for pyout to know that bool True should be this or that
    """
$> datalad ls -rLa  ~/datalad/openfmri/ds000001
[ERROR  ] 'ascii' codec can't decode byte 0xe2 in position 0: ordinal not in \
range(128) [tabular.py:_writerow:333] (UnicodeDecodeError)

But for DANDI we will  be brave
    """
    return u"✓" if v else "-"
    # return 'X' if v else '-'


def naturalsize(v):
    if v in ["", None]:
        return ""
    return humanize.naturalsize(v)


def datefmt(v, fmt=u"%Y-%m-%d/%H:%M:%S"):
    if isinstance(v, datetime.datetime):
        return v.strftime(fmt)
    else:
        time.strftime(fmt, time.localtime(v))


def empty_for_none(v):
    return "" if v is None else v


def summary_dates(values):
    return (
        ["%s>" % datefmt(min(values)), "%s<" % datefmt(max(values))] if values else []
    )


def counts(values):
    return ["{:d} {}".format(v, k) for k, v in Counter(values).items()]


def minmax(values, fmt="%s"):
    if not values:
        return []
    mi = min(values)
    ma = max(values)

    if mi != ma:
        return [(fmt + ">") % min(values), (fmt + "<") % max(values)]
    else:
        return fmt % mi


class mapped_counts(object):
    def __init__(self, mapping):
        self._mapping = mapping

    def __call__(self, values):
        mapped = [self._mapping.get(v, v) for v in values]
        return counts(mapped)


size_style = dict(
    transform=naturalsize,
    color=dict(
        interval=[
            [0, 1024, "blue"],
            [1024, 1024 ** 2, "green"],
            [1024 ** 2, None, "red"],
        ]
    ),
    aggregate=lambda x: naturalsize(sum(x)),
    # summary=sum,
)

PYOUT_SHORT_NAMES = {
    # shortening for some fields
    "nwb_version": "NWB",
    # 'annex_local_size': 'annex(present)',
    # 'annex_worktree_size': 'annex(worktree)',
}
for f in metadata_nwb_fields + metadata_dandiset_fields:
    if f.startswith("number_of_"):
        PYOUT_SHORT_NAMES[f] = f.replace("number_of_", "#")

# For reverse lookup
PYOUT_SHORT_NAMES_rev = {v.lower(): k for k, v in PYOUT_SHORT_NAMES.items()}


def get_style(hide_if_missing=True):
    progress_style = dict(  # % done
        transform=lambda f: "%d%%" % f,
        align="right",
        color=dict(
            interval=[[0, 10, "red"], [10, 100, "yellow"], [100, None, "green"]]
        ),
    )
    STYLE = {
        "summary_": {"bold": True},
        "header_": dict(
            bold=True, transform=lambda x: PYOUT_SHORT_NAMES.get(x, x).upper()
        ),
        "default_": dict(missing=""),
        "path": dict(
            bold=True,
            align="left",
            underline=True,
            width=dict(
                truncate="left",
                min=20,
                # min=max_filename_len + 4 #  .../
                # min=0.3  # not supported yet by pyout,
                # https://github.com/pyout/pyout/issues/85
            ),
            aggregate=lambda _: "Summary:"
            # TODO: seems to be wrong
            # width='auto'
            # summary=lambda x: "TOTAL: %d" % len(x)
        ),
        # ('type', dict(
        #     transform=lambda s: "%s" % s,
        #     aggregate=counts,
        #     missing='-',
        #     # summary=summary_counts
        # )),
        # ('describe', dict(
        #     transform=empty_for_none)),
        # ('clean', dict(
        #     color='green',
        #     transform=fancy_bool,
        #     aggregate=mapped_counts({False: fancy_bool(False),
        #                              True: fancy_bool(True)}),
        #     delayed="group-git"
        # )),
        "size": dict(size_style),
        "nwb_version": {},  # Just to establish the order
        "session_start_time": dict(
            transform=datefmt,
            aggregate=summary_dates,
            # summary=summary_dates
        ),
        "errors": dict(
            align="center",
            color=dict(interval=[[0, 1, "green"], [1, None, "red"]]),
            aggregate=lambda x: (
                "{} with errors".format(sum(map(bool, x))) if any(x) else ""
            ),
        ),
        "status": dict(
            color=dict(lookup={"skipped": "yellow", "done": "green", "error": "red"}),
            aggregate=counts,
        ),
        "message": dict(
            color=dict(
                re_lookup=[["^exists", "yellow"], ["^(failed|error|ERROR)", "red"]]
            ),
            aggregate=counts,
        ),
        "upload": progress_style,
        "done%": progress_style,
        "checksum": dict(
            align="center",
            color=dict(
                re_lookup=[
                    ["ok", "green"],
                    ["^(-|NA|N/A)", "yellow"],
                    ["^(differ|failed|error|ERROR)", "red"],
                ]
            ),
        ),
    }
    if hide_if_missing:
        # To just quickly switch for testing released or not released (with
        # hide)
        # pyout
        if "hide" in pyout.elements.schema["definitions"]:
            lgr.debug("pyout with 'hide' support detected")
            STYLE["default_"]["hide"] = "if_missing"
            # to avoid https://github.com/pyout/pyout/pull/102
            for f in STYLE:
                if not f.endswith("_"):
                    STYLE[f]["hide"] = "if_missing"
            # but make always visible for some
            for f in ("path",):
                STYLE[f]["hide"] = False
        else:
            lgr.warning("pyout without 'hide' support. Expect too many columns")

    if not sys.stdout.isatty():
        # TODO: ATM width in the final mode is hardcoded
        #  https://github.com/pyout/pyout/issues/70
        # and depending on how it would be resolved, there might be a
        # need to specify it here as "max" or smth like that.
        # For now hardcoding to hopefully wide enough 200 if stdout is not
        # a tty
        STYLE["width_"] = 200

    return STYLE


def exclude_all(r):
    return False


class LogSafeTabular(pyout.Tabular):
    def __enter__(self):
        super().__enter__()
        root = logging.getLogger()
        for h in root.handlers:
            # Use `type()` instead of `isinstance()` because FileHandler is a
            # subclass of StreamHandler, and we don't want to disable it:
            if type(h) is logging.StreamHandler:
                h.addFilter(exclude_all)
        return self

    def __exit__(self, exc_type, exc_value, tb):
        try:
            super().__exit__(exc_type, exc_value, tb)
        finally:
            root = logging.getLogger()
            for h in root.handlers:
                # Use `type()` instead of `isinstance()` because FileHandler is
                # a subclass of StreamHandler, and we don't want to disable it:
                if type(h) is logging.StreamHandler:
                    h.removeFilter(exclude_all)
