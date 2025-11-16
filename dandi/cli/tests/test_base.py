import re

import click
import pytest

from dandi.cli.base import _compile_regex, parse_regexes

DUMMY_CTX = click.Context(click.Command("dummy"))
DUMMY_PARAM = click.Option(["--dummy"])


class TestCompileRegex:
    @pytest.mark.parametrize(
        "pattern",
        [
            "abc",
            "[a-z]+",
            "^start$",
            r"a\.b",
        ],
    )
    def test_valid_patterns_return_pattern(self, pattern):
        compiled = _compile_regex(pattern)
        assert isinstance(compiled, re.Pattern)
        assert compiled.pattern == pattern

    @pytest.mark.parametrize("pattern", ["(", "[a-z", "\\"])
    def test_invalid_patterns_raise_bad_parameter(self, pattern):
        with pytest.raises(click.BadParameter) as exc_info:
            _compile_regex(pattern)
        msg = str(exc_info.value)
        assert "Invalid regex pattern" in msg
        assert repr(pattern) in msg


class TestParseRegexes:
    def test_none_returns_none(self):
        assert parse_regexes(DUMMY_CTX, DUMMY_PARAM, None) is None

    @pytest.mark.parametrize(
        "value",
        [
            "abc",
            "[a-z]+",
            r"a\.b",
            r"",
        ],
    )
    def test_single_pattern(self, value):

        result = parse_regexes(DUMMY_CTX, DUMMY_PARAM, value)
        assert isinstance(result, list)
        assert len(result) == 1

        (compiled,) = result
        assert isinstance(compiled, re.Pattern)
        assert compiled.pattern == value

    @pytest.mark.parametrize(
        "value, expected_patterns_in_strs",
        [
            ("foo,,bar", ["foo", "", "bar"]),
            ("^start$,end$", ["^start$", "end$"]),
            (r"a\.b,c+d", [r"a\.b", r"c+d"]),
            # duplicates should be collapsed by the internal set()
            ("foo,foo,bar", ["foo", "bar"]),
        ],
    )
    def test_multiple_patterns(self, value: str, expected_patterns_in_strs: list[str]):
        result = parse_regexes(DUMMY_CTX, DUMMY_PARAM, value)
        assert isinstance(result, list)

        # Order is not guaranteed due to de-duplication via set
        # So we just check that all expected patterns are present
        assert {p.pattern for p in result} == set(expected_patterns_in_strs)

    @pytest.mark.parametrize(
        "value, bad_pattern", [("(", "("), ("foo,(", "("), ("good,[a-z", "[a-z")]
    )
    def test_invalid_pattern_raises_bad_parameter(self, value: str, bad_pattern: str):
        with pytest.raises(click.BadParameter, match=re.escape(bad_pattern)):
            parse_regexes(DUMMY_CTX, DUMMY_PARAM, value)
