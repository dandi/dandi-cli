import pytest
from ..metadata import parse_age


@pytest.mark.parametrize(
    "age,duration",
    [
        ("5y", "P5Y"),
        ("5Y", "P5Y"),
        ("5 years", "P5Y"),
        ("1year", "P1Y"),
        ("0y", "P0Y"),
        ("2 months", "P2M"),
        ("2 M", "P2M"),
        ("2 m", "P2M"),
        ("2M", "P2M"),
        ("2m", "P2M"),
        ("3 weeks", "P3W"),
        ("3 w", "P3W"),
        ("3 W", "P3W"),
        ("3w", "P3W"),
        ("3W", "P3W"),
        ("0 days", "P0D"),
        ("7 d", "P7D"),
        ("7 D", "P7D"),
        ("7d", "P7D"),
        ("7D", "P7D"),
    ],
)
def test_parse_age(age, duration):
    assert parse_age(age) == duration
