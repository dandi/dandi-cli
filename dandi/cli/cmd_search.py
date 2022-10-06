from pathlib import Path

import click
import pandas as pd
import stardog

from .base import map_to_click_exceptions

DANDISETS_FIELDS = {
    "approach": ["apr", "?as dandi:approach / schema:name ?apr ."],
    "species_id": ["sid", "?as dandi:species / schema:identifier ?sid ."],
    "species_name": ["snm", "?as dandi:species / schema:name ?snm ."],
}

# The use of f-strings apparently makes this not a proper docstring, and so
# click doesn't use it unless we explicitly assign it to `help`:


@click.command(help="Search TODO")
@click.option(
    "-F",
    "--file",
    help="Comma-separated list of fields to display. "
    "An empty value to trigger a list of "
    "available fields to be printed out",
)
@click.option(
    "-t",
    "--search_type",
    help="Type of the search.",
    type=click.Choice(["dandisets", "assets"]),
)
@click.option(
    "--check_fields",
    help="Field name for dandisets search",
    type=click.Choice(DANDISETS_FIELDS.keys()),
    multiple=True,
)
@click.option(
    "--filter_fields",
    help="Field name for dandisets search",
    type=(str, str),
    multiple=True,
)
@click.option(
    "-f",
    "--format",
    help="Choose the format for output. TODO",
    type=click.Choice(["stdout", "csv"]),
    default="stdout",
)
@click.option(
    "--number_of_lines",
    help="Number of lines of output that will be printed",
    default=10,
)
@click.option(
    "-d",
    "--database_name",
    help="Database name",
    default="dandisets_new",
)
@map_to_click_exceptions
def search(
    file=None,
    search_type=None,
    check_fields=None,
    filter_fields=None,
    format="stdout",
    number_of_lines=10,
    database_name="dandisets_new",
):

    if file and search_type:
        raise Exception("file and type are mutually exclusive options")

    conn_details = {
        "endpoint": "https://search.dandiarchive.org:5820",
        "username": "anonymous",
        "password": "anonymous",
    }

    if file:
        filepath = Path(file)
        with filepath.open() as f:
            query_str = f.read()
    elif search_type == "dandisets":
        if not check_fields and not filter_fields:
            raise Exception(
                "check_fields or filter_fields is required if search type is dandisets"
            )
        elif filter_fields:
            for el in filter_fields:
                if el[0] not in DANDISETS_FIELDS:
                    raise Exception(
                        f"field {el[0]} used in filter_fields, but only {DANDISETS_FIELDS} allowed"
                    )
        query_str = create_dandiset_query(check_fields, filter_fields)
    else:
        raise NotImplementedError

    with stardog.Connection(database_name, **conn_details) as conn:
        results = conn.select(query_str)
    res_df = results2df(results, number_of_lines)

    if format == "stdout":
        print(res_df)
    else:
        raise NotImplementedError("only stdout format implemented for now")

    # errors = defaultdict(list)  # problem: [] paths
    #
    # if errors:
    #     lgr.warning(
    #         "Failed to operate on some paths (empty records were listed):\n %s",
    #         "\n ".join("%s: %d paths" % (k, len(v)) for k, v in errors.items()),
    #     )


def results2df(results, limit=10):
    res_lim = results["results"]["bindings"][:limit]
    res_val_l = [dict((k, v["value"]) for k, v in res.items()) for res in res_lim]
    return pd.DataFrame(res_val_l)


def create_dandiset_query(check_fields, filter_fields):
    var = ""
    for el in check_fields:
        var += f" ?{DANDISETS_FIELDS[el][0]}"

    query_str = (
        f"SELECT DISTINCT ?d{var} WHERE \n" "{ \n" "   ?d dandi:assetsSummary ?as . \n"
    )
    for el in check_fields:
        query_str += f"   {DANDISETS_FIELDS[el][1]} \n"

    for (key, val) in filter_fields:
        query_str += f'FILTER (?{DANDISETS_FIELDS[key][0]} = "{val}") \n'
    query_str += "}"
    # print(query_str)
    return query_str
