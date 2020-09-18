from pathlib import Path
import subprocess
from urllib.parse import urlparse
import click
import requests
from dandi import girder
from dandi.dandiarchive import navigate_url
from dandi.utils import get_instance


@click.command()
@click.option("-i", "--ignore-errors", is_flag=True)
@click.argument("assetstore", type=click.Path(exists=True, file_okay=False))
@click.argument("target", type=click.Path(file_okay=False))
def main(assetstore, target, ignore_errors):
    instantiate_dandisets(Path(assetstore), Path(target), ignore_errors)


def instantiate_dandisets(
    assetstore_path: Path, target_path: Path, ignore_errors=False
):
    with requests.Session() as s:
        for did in get_dandiset_ids():
            dsdir = target_path / did
            dsdir.mkdir(parents=True, exist_ok=True)
            with navigate_url(f"https://dandiarchive.org/dandiset/{did}/draft") as (
                _,
                _,
                assets,
            ):
                for a in assets:
                    gid = a["girder"]["id"]
                    src = assetstore_path / girderid2assetpath(s, gid)
                    dest = dsdir / a["path"].lstrip("/")
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    print(src, "->", dest)
                    try:
                        mklink(src, dest)
                    except Exception:
                        if not ignore_errors:
                            raise


def get_dandiset_ids():
    dandi_instance = get_instance("dandi")
    client = girder.get_client(dandi_instance.girder, authenticate=False)
    offset = 0
    per_page = 50
    while True:
        dandisets = client.get(
            "dandi", parameters={"limit": per_page, "offset": offset}
        )
        if not dandisets:
            break
        for d in dandisets:
            yield d["meta"]["dandiset"]["identifier"]
        offset += len(dandisets)


def girderid2assetpath(session, girder_id):
    r = session.head(
        f"https://girder.dandiarchive.org/api/v1/file/{girder_id}/download"
    )
    r.raise_for_status()
    return urlparse(r.headers["Location"]).path.lstrip("/")


def mklink(src, dest):
    subprocess.run(
        ["cp", "-L", "--reflink=always", "--remove-destination", str(src), str(dest)],
        check=True,
    )


if __name__ == "__main__":
    main()
