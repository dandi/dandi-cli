import datetime
import sys


class JSONFormatter(object):
    def __init__(self, indent=None, out=sys.stdout):
        self.indent = indent
        self.out = out

    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_value, traceback):
        pass

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


class YAMLFormatter(object):
    def __init__(self, out=sys.stdout):
        self.out = out
        self.records = []

    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_value, traceback):
        import yaml

        self.out.write(yaml.dump(self.records))

    def __call__(self, rec):
        self.records.append(rec)
