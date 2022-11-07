from click.testing import CliRunner
import pytest

from dandi.tests.skip import mark

from ..command import search

pytestmark = mark.skipif_no_network


@pytest.mark.parametrize(
    "select_fields, print_fields",
    [
        ("approach", ["app"]),
        ("species_name", ["snm"]),
    ],
)
def test_search_dandiset_select_fields(select_fields, print_fields):
    """using select_fields option with single or multiple comma-separated values"""
    runner = CliRunner()
    r = runner.invoke(search, ["-t", "dandisets", "--select_fields", select_fields])
    assert r.exit_code == 0, f"Exited abnormally. out={r.stdout}"
    out = r.stdout
    for fld in print_fields:
        assert fld in out, f"{fld} is not in the output: {out}"


@pytest.mark.parametrize(
    "select_fields_mult",
    [
        (["--select_fields", "approach", "-s", "species_name"]),
        (["--select_fields", "approach,species_name"]),
    ],
)
def test_search_dandiset_select_fields_mult(select_fields_mult):
    """using select_fields option multiple times"""
    runner = CliRunner()
    r = runner.invoke(search, ["-t", "dandisets"] + select_fields_mult)
    assert r.exit_code == 0, f"Exited abnormally. out={r.stdout}"
    out = r.stdout
    for fld in ["apr", "snm"]:
        assert fld in out, f"field {fld} is not in the output"


@pytest.mark.parametrize(
    "filter_fields", [["species_name", "Human"], ["approach", "behavioral approach"]]
)
def test_search_dandiset_check_filter(filter_fields):
    """using select_fields option multiple times"""
    runner = CliRunner()
    r = runner.invoke(
        search,
        [
            "-t",
            "dandisets",
            "--select_fields",
            "approach,species_name",
            "--filter_fields",
        ]
        + filter_fields,
    )
    assert r.exit_code == 0, f"Exited abnormally. out={r.stdout}"
    out = r.stdout
    for ln in out.split("\n")[1:]:
        if ln == "":
            break
        assert filter_fields[1] in ln, f"value {filter_fields[1]} is not in the output"


def test_search_dandiset_check_filter_mult():
    """using a filter option multiple times"""
    runner = CliRunner()
    r = runner.invoke(
        search,
        [
            "-t",
            "dandisets",
            "--select_fields",
            "approach,species_name",
            "-f",
            "species_name",
            "Human",
            "-f",
            "approach",
            "behavioral approach",
        ],
    )
    assert r.exit_code == 0, f"Exited abnormally. out={r.stdout}"
    out = r.stdout
    for ln in out.split("\n")[1:-1]:
        assert "Human" in ln, "Human is not in the output"
        assert "behavioral approach" in ln, "behavioral approach is not in the output"


def test_search_dandiset_check_filter_list():
    """using comma-separated list in a filter option"""
    runner = CliRunner()
    r = runner.invoke(
        search,
        [
            "-t",
            "dandisets",
            "--select_fields",
            "approach,species_name",
            "-f",
            "species_name",
            "Human,House mouse",
        ],
    )
    assert r.exit_code == 0, f"Exited abnormally. out={r.stdout}"
    out = r.stdout
    for ln in out.split("\n")[1:-1]:
        assert "Human" in ln or "House mouse" in ln, "Human is not in the output"


@pytest.mark.parametrize(
    "select_fields, print_fields",
    [("format", ["format"]), ("size", ["size"]), ("size,format", ["size", "format"])],
)
def test_search_assets_select_fields(select_fields, print_fields):
    """using select_fields option with single or multiple comma-separated values"""
    runner = CliRunner()
    r = runner.invoke(search, ["-t", "assets", "--select_fields", select_fields])
    assert r.exit_code == 0, f"Exited abnormally. out={r.stdout}"
    out = r.stdout
    for fld in print_fields:
        assert fld in out, f"{fld} is not in the output: {out}"


@pytest.mark.parametrize(
    "filter_fields",
    [
        ["format", "application/x-nwb"],
    ],
)
def test_search_asset_check_filter(filter_fields):
    """using select_fields and filter option in assets search"""
    runner = CliRunner()
    r = runner.invoke(
        search,
        ["-t", "assets", "--select_fields", "format,size", "--filter_fields"]
        + filter_fields,
    )
    assert r.exit_code == 0, f"Exited abnormally. out={r.stdout}"
    out = r.stdout
    for ln in out.split("\n")[1:]:
        if ln == "":
            break
        assert filter_fields[1] in ln, f"value {filter_fields[1]} is not in the output"


@pytest.mark.parametrize(
    "size_range", [(7 * 10e9, 9 * 10e9), "(, 9*10e9)", "(7*10e9, )"]
)
def test_search_asset_check_filter_range(size_range):
    """using range in a filter option for assets search"""
    runner = CliRunner()
    r = runner.invoke(
        search,
        [
            "-t",
            "assets",
            "--select_fields",
            "format,size",
            "--filter_fields",
            "size",
            f"{size_range}",
        ],
    )
    assert r.exit_code == 0, f"Exited abnormally. out={r.stdout}"
    out = r.stdout
    assert "size" in out.split("\n")[0]
    assert len(out.split("\n")) > 1


def test_search_from_file(tmpdir):
    """using search command with a file that contains any sprql query"""
    query_file = tmpdir / "query.txt"
    query = """
    SELECT DISTINCT ?apr WHERE
    {
    ?as dandi:approach / schema:name ?apr
    }
    """
    with query_file.open("w") as f:
        f.write(query)
    runner = CliRunner()
    r = runner.invoke(search, ["-F", query_file])
    assert r.exit_code == 0, f"Exited abnormally. out={r.stdout}"
    out = r.stdout
    assert "apr" in out.split("\n")[0]
    assert len(out.split("\n")) > 1
