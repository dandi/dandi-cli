from pathlib import Path

import click
import pandas as pd
import stardog

from .base import map_to_click_exceptions

# supported fields
# TODO: adding more
DANDISETS_FIELDS = {
    "approach": ["apr", "?as dandi:approach / schema:name ?apr ."],
    "species_id": ["sid", "?as dandi:species / schema:identifier ?sid ."],
    "species_name": ["snm", "?as dandi:species / schema:name ?snm ."],
}

ASSETS_FIELDS = {
    "size": ["size", "?asset schema:contentSize ?size ."],
    "format": ["format", "?asset schema:encodingFormat ?format ."],
}


def parse_validate(ctx, param, value):
    value_parse = []
    # parsing elements that have multiple comma-separated values
    for el in value:
        value_parse += el.split(",")
    if param.name == "select_fields":
        if ctx.params["search_type"] == "dandisets":
            choice_list = DANDISETS_FIELDS.keys()
        elif ctx.params["search_type"] == "assets":
            choice_list = ASSETS_FIELDS.keys()
        else:
            choice_list = None
    else:
        choice_list = None
    # checking if all values are in the list of possible choices
    for el in value_parse:
        if choice_list and el not in choice_list:
            ctx.fail(f"{el} is not in the list: {choice_list}")
    return value_parse


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
    "-s",
    "--select_fields",
    help="Field name for dandisets search",
    callback=parse_validate,
    multiple=True,
)
@click.option(
    "-f",
    "--filter_fields",
    help="Field name for dandisets search",
    type=(str, str),
    multiple=True,
)
@click.option(
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
    select_fields=None,
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
    elif search_type in ["dandisets", "assets"]:
        if not select_fields:
            raise Exception(
                f"select_fields is required if search type is {search_type}"
            )
        if filter_fields:
            for el in filter_fields:
                if el[0] not in select_fields:
                    raise Exception(
                        f"field {el[0]} used in filter_fields, "
                        f"but select fields contain {select_fields}"
                    )
        if search_type == "dandisets":
            query_str = create_dandisets_query(select_fields, filter_fields)
        elif search_type == "assets":
            query_str = create_assets_query(select_fields, filter_fields)
    else:
        raise NotImplementedError

    with stardog.Connection(database_name, **conn_details) as conn:
        results = conn.select(query_str)
    res_df = results2df(results, number_of_lines)

    if format == "stdout":
        print(res_df)
    else:
        raise NotImplementedError("only stdout format implemented for now")


def results2df(results, limit=10):
    res_lim = results["results"]["bindings"][:limit]
    res_val_l = [dict((k, v["value"]) for k, v in res.items()) for res in res_lim]
    return pd.DataFrame(res_val_l)


def filter_query(filter_fields, fields_dict):
    """creating filter part for the queries"""
    filter_str = ""
    for (key, val) in filter_fields:
        if val[0] == "(" and val[-1] == ")":
            val = val[1:-1].split(",")
            if len(val) != 2:
                raise ValueError(
                    "If value for filter is a tuple, it has to have 2 elements "
                )
            else:
                min_val = val[0].strip()
                max_val = val[1].strip()
                if max_val and min_val:
                    filter_str += (
                        f"FILTER (?{fields_dict[key][0]} > {min_val} "
                        f"&& ?{fields_dict[key][0]} < {max_val}) \n"
                    )
                elif max_val:
                    filter_str += f"FILTER (?{fields_dict[key][0]} < {max_val}) \n"
                elif min_val:
                    filter_str += f"FILTER (?{fields_dict[key][0]} > {min_val}) \n"
        else:
            val = val.split(",")
            cond_str = f'?{fields_dict[key][0]} = "{val[0]}"'
            for el in val[1:]:
                cond_str += f' || ?{fields_dict[key][0]} = "{el}"'
            filter_str += f"FILTER ({cond_str}) \n"
    return filter_str


def create_dandisets_query(select_fields, filter_fields):
    """Creating a query for dandisets search"""
    var = ""
    for el in select_fields:
        var += f" ?{DANDISETS_FIELDS[el][0]}"

    query_str = (
        f"SELECT DISTINCT ?d{var} WHERE \n" "{ \n" "   ?d dandi:assetsSummary ?as . \n"
    )
    for el in select_fields:
        query_str += f"   {DANDISETS_FIELDS[el][1]} \n"
    query_str += filter_query(filter_fields, DANDISETS_FIELDS)
    query_str += "}"
    return query_str


def create_assets_query(select_fields, filter_fields):
    """Creating a query for assets search"""
    var = ""
    for el in select_fields:
        var += f" ?{ASSETS_FIELDS[el][0]}"

    query_str = (
        f"SELECT DISTINCT ?asset ?d_id ?path{var} WHERE \n"
        "{ \n"
        "   ?asset rdf:type dandi:Asset . \n"
        "   ?d prov:hasMember ?asset . \n"
        "   ?d schema:identifier ?d_id . \n"
        "   ?asset dandi:path ?path . \n"
    )
    for el in select_fields:
        query_str += f"   {ASSETS_FIELDS[el][1]} \n"
    query_str += filter_query(filter_fields, ASSETS_FIELDS)
    query_str += "}"
    return query_str
