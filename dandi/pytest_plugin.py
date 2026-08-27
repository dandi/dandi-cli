from __future__ import annotations

from importlib.metadata import PackageNotFoundError, requires, version

from dandischema.models import DandiBaseModel
from packaging.requirements import Requirement
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


def pytest_configure(config):
    markers = [
        "integration",
        "obolibrary",
        "flaky",
        "ai_generated",
    ]
    for marker in markers:
        config.addinivalue_line("markers", marker)


def pytest_report_header(config: Config) -> list[str]:
    """Add version information for key dependencies to the pytest header."""
    try:
        # Extract package names from requirement strings.
        # Format: "package-name >= 1.0" or "package-name ; condition"
        #  and by regex thus we skip extras (in square brackets like [test])
        deps = {Requirement(dep).name for dep in (requires("dandi") or [])}
    except PackageNotFoundError:
        # Use defaults if we didn't get deps from metadata
        deps = {"dandischema", "h5py", "hdmf"}

    # Format versions for display (sorted for consistent output)
    versions = []
    for pkg in sorted(deps):
        try:
            version_str = f"-{version(pkg)}"
        except PackageNotFoundError:
            version_str = " NOT INSTALLED"
        versions.append(f"{pkg}{version_str}")

    return [f"dependencies: {', '.join(versions)}"] if versions else []


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


def pytest_assertrepr_compare(op, left, right):
    """Custom comparison representation for your classes."""
    if (
        isinstance(left, DandiBaseModel)
        and isinstance(right, DandiBaseModel)
        and op == "=="
    ):
        ldict, rdict = dict(left), dict(right)
        if ldict == rdict:
            return [
                "dict representations of models are equal, but values aren't!",
                f"Left: {left!r}",
                f"Right: {right!r}",
            ]
        else:
            # Rely on pytest just "recursing" into interpreting the dict fails
            # TODO: could be further improved by account for ANY values etc
            assert ldict == rdict  # for easier comprehension of diffs
    return None
