from io import StringIO

import pytest

from ..formatter import JSONFormatter, JSONLinesFormatter


def test_json_formatter():
    out = StringIO()
    fmtr = JSONFormatter(out=out)
    with fmtr:
        fmtr({"foo": 23, "bar": 42})
        fmtr({"bar": "gnusto", "foo": "cleesh"})
    assert out.getvalue() == (
        "[\n"
        '  {"bar": 42, "foo": 23},\n'
        '  {"bar": "gnusto", "foo": "cleesh"}\n'
        "]\n"
    )


def test_json_formatter_indented():
    out = StringIO()
    fmtr = JSONFormatter(indent=2, out=out)
    with fmtr:
        fmtr({"foo": 23, "bar": 42})
        fmtr({"bar": "gnusto", "foo": "cleesh"})
    assert out.getvalue() == (
        "[\n"
        "  {\n"
        '    "bar": 42,\n'
        '    "foo": 23\n'
        "  },\n"
        "  {\n"
        '    "bar": "gnusto",\n'
        '    "foo": "cleesh"\n'
        "  }\n"
        "]\n"
    )


@pytest.mark.parametrize("indent", [None, 2])
def test_json_formatter_empty(indent):
    out = StringIO()
    fmtr = JSONFormatter(indent=indent, out=out)
    with fmtr:
        pass
    assert out.getvalue() == "[]\n"


def test_json_lines_formatter():
    out = StringIO()
    fmtr = JSONLinesFormatter(out=out)
    with fmtr:
        fmtr({"foo": 23, "bar": 42})
        fmtr({"bar": "gnusto", "foo": "cleesh"})
    assert out.getvalue() == (
        '{"bar": 42, "foo": 23}\n{"bar": "gnusto", "foo": "cleesh"}\n'
    )


def test_json_lines_formatter_empty():
    out = StringIO()
    fmtr = JSONLinesFormatter(out=out)
    with fmtr:
        pass
    assert out.getvalue() == ""
