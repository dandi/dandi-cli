"""pyout support helpers
"""
import datetime
import time
import humanize
from collections import Counter


def fancy_bool(v):
    # TODO: move such supports into pyout since we should not
    # investigate here either terminal/output supports ANSI
    # should be for pyout to know that bool True should be this or that
    """
$> datalad ls -rLa  ~/datalad/openfmri/ds000001
[ERROR  ] 'ascii' codec can't decode byte 0xe2 in position 0: ordinal not in range(128) [tabular.py:_writerow:333] (UnicodeDecodeError)

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
