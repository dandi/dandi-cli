from __future__ import annotations

from pytest import Config, Item, Parser

from .tests.fixtures import *  # noqa: F401, F403  # lgtm [py/polluting-import]


def pytest_addoption(parser: Parser) -> None:
    parser.addoption(
        "--dandi-api",
        action="store_true",
        default=False,
        help="Only run tests of the new Django DANDI API",
    )
    parser.addoption(
        "--scheduled",
        action="store_true",
        default=False,
        help="Use configuration for a scheduled daily test run",
    )


def pytest_collection_modifyitems(items: list[Item], config: Config) -> None:
    # Based on <https://pythontesting.net/framework/pytest/pytest-run-tests
    # -using-particular-fixture/>
    if config.getoption("--dandi-api"):
        selected_items = []
        deselected_items = []
        for item in items:
            if "local_dandi_api" in getattr(item, "fixturenames", ()):
                selected_items.append(item)
            else:
                deselected_items.append(item)
        config.hook.pytest_deselected(items=deselected_items)
        items[:] = selected_items
