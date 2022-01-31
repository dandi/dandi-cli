from typing import List

from _pytest.config import Config
from _pytest.config.argparsing import Parser
from _pytest.nodes import Item

from .tests.fixtures import *  # noqa: F401, F403  # lgtm [py/polluting-import]


def pytest_addoption(parser: Parser) -> None:
    parser.addoption(
        "--dandi-api",
        action="store_true",
        default=False,
        help="Only run tests of the new Django Dandi API",
    )


def pytest_collection_modifyitems(items: List[Item], config: Config) -> None:
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
