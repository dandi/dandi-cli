#!/usr/bin/env python3
import click
import requests

from dandi.dandiapi import DandiAPIClient
from dandi.dandiset import APIDandiset


@click.command()
@click.option(
    "-d", "--delete-extant", is_flag=True, help="Delete Dandisets that already exist"
)
@click.argument("api_url")
@click.argument("token")
@click.argument("dandiset_path", nargs=-1)
def main(api_url, token, dandiset_path, delete_extant):
    client = DandiAPIClient(api_url=api_url, token=token)
    with client.session():
        for dpath in dandiset_path:
            dandiset = APIDandiset(dpath)
            if delete_extant:
                try:
                    client.get_dandiset(dandiset.identifier, "draft")
                except requests.HTTPError as e:
                    if e.response.status_code != 404:
                        raise
                else:
                    print("Dandiset", dandiset.identifier, "already exists; deleting")
                    client.delete(f"/dandisets/{dandiset.identifier}/")
            print("Creating Dandiset", dandiset.identifier)
            client.create_dandiset(
                name=dandiset.metadata.get("name", ""), metadata=dandiset.metadata
            )


if __name__ == "__main__":
    main()
