import datetime
import os.path as op
import sys

import pyout
from ..support import pyout as pyouts

from .. import get_logger

lgr = get_logger()


class Formatter(object):
    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_value, traceback):
        pass

    def __call__(self, rec):
        pass


class JSONFormatter(Formatter):
    def __init__(self, indent=None, out=None):
        self.out = out or sys.stdout
        self.indent = indent

    @staticmethod
    def _serializer(o):
        if isinstance(o, datetime.datetime):
            return o.__str__()
        return o

    def __call__(self, rec):
        import json

        self.out.write(
            json.dumps(rec, indent=self.indent, default=self._serializer) + "\n"
        )


class YAMLFormatter(Formatter):
    def __init__(self, out=None):
        self.out = out or sys.stdout
        self.records = []

    def __exit__(self, exc_type, exc_value, traceback):
        import yaml

        self.out.write(yaml.dump(self.records))

    def __call__(self, rec):
        self.records.append(rec)


PYOUT_SHORT_NAMES = {
    # shortening for some fields
    "nwb_version": "NWB",
    "number_of_electrodes": "#electrodes",
    "number_of_units": "#units",
    # 'annex_local_size': 'annex(present)',
    # 'annex_worktree_size': 'annex(worktree)',
}
# For reverse lookup
PYOUT_SHORT_NAMES_rev = {v.lower(): k for k, v in PYOUT_SHORT_NAMES.items()}


class PYOUTFormatter(pyout.Tabular):
    def __init__(self, files, fields):
        max_filename_len = max(map(lambda x: len(op.basename(x)), files))
        # Needs to stay here due to use of  counts/mapped_counts
        PYOUT_STYLE = {
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
            "size": dict(pyouts.size_style),
            "nwb_version": {},  # Just to establish the order
            "session_start_time": dict(
                transform=pyouts.datefmt,
                aggregate=pyouts.summary_dates,
                # summary=summary_dates
            ),
        }
        # To just quickly switch for testing released or not released (with
        # hide)
        # pyout
        if "hide" in pyout.elements.schema["definitions"]:
            lgr.debug("pyout with 'hide' support detected")
            PYOUT_STYLE["default_"]["hide"] = "if_missing" if not fields else False
            for f in "path", "size":
                PYOUT_STYLE[f]["hide"] = False
        else:
            lgr.warning("pyout without 'hide' support. Expect too many columns")

        if not sys.stdout.isatty():
            # TODO: ATM width in the final mode is hardcoded
            #  https://github.com/pyout/pyout/issues/70
            # and depending on how it would be resolved, there might be a
            # need to specify it here as "max" or smth like that.
            # For now hardcoding to hopefully wide enough 200 if stdout is not
            # a tty
            PYOUT_STYLE["width_"] = 200

        kw = dict(style=PYOUT_STYLE)
        if fields:
            kw["columns"] = fields
        super().__init__(**kw)
