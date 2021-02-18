import datetime
import sys

from .. import get_logger
from ..support import pyout as pyouts

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
            json.dumps(
                rec, indent=self.indent, sort_keys=True, default=self._serializer
            )
            + "\n"
        )


class YAMLFormatter(Formatter):
    def __init__(self, out=None):
        self.out = out or sys.stdout
        self.records = []

    def __exit__(self, exc_type, exc_value, traceback):
        import ruamel.yaml

        yaml = ruamel.yaml.YAML(typ="safe")
        yaml.default_flow_style = False
        yaml.dump(self.records, self.out)

    def __call__(self, rec):
        self.records.append(rec)


class PYOUTFormatter(pyouts.LogSafeTabular):
    def __init__(self, fields, **kwargs):
        PYOUT_STYLE = pyouts.get_style(hide_if_missing=not fields)

        kw = dict(style=PYOUT_STYLE)
        kw.update(kwargs)
        if fields:
            kw["columns"] = fields
        super().__init__(**kw)
