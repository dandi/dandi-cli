import datetime
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


class PYOUTFormatter(pyout.Tabular):
    def __init__(self, fields):
        PYOUT_STYLE = pyouts.get_style(hide_if_missing=not fields)

        kw = dict(style=PYOUT_STYLE)
        if fields:
            kw["columns"] = fields
        super().__init__(**kw)
