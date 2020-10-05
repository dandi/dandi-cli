from pathlib import Path
import subprocess
from urllib.parse import urlparse
import click
from dandi import girder
from dandi.consts import dandiset_metadata_file
from dandi.dandiarchive import navigate_url
from dandi.dandiset import Dandiset
from dandi.utils import get_instance
from datalad.api import Dataset
import requests


@click.command()
@click.option("-i", "--ignore-errors", is_flag=True)
@click.argument("assetstore", type=click.Path(exists=True, file_okay=False))
@click.argument("target", type=click.Path(file_okay=False))
def main(assetstore, target, ignore_errors):
    DatasetInstantiator(Path(assetstore), Path(target), ignore_errors).run()


class DatasetInstantiator:
    def __init__(self, assetstore_path: Path, target_path: Path, ignore_errors=False):
        self.assetstore_path = assetstore_path
        self.target_path = target_path
        self.ignore_errors = ignore_errors
        self.session = None

    def run(self):
        self.target_path.mkdir(parents=True, exist_ok=True)
        with requests.Session() as self.session:
            for did in self.get_dandiset_ids():
                ds = Dataset(str(self.target_path / did))
                if not ds.is_installed():
                    ds.create(cfg_proc="text2git")
                    ds.config.set("annex.backends", "SHA256E", where="local")
                gitattrs = ds.pathobj / ".gitattributes"
                gitattrs.write_text(gitattrs.read_text().replace("MD5E", "SHA256E"))
                self.sync_dataset(did, ds)

    def sync_dataset(self, dandiset_id, ds):
        def get_annex_hash(file):
            return ds.repo.get_file_key(file).split("-")[-1].partition(".")[0]

        with navigate_url(f"https://dandiarchive.org/dandiset/{dandiset_id}/draft") as (
            _,
            dandiset,
            assets,
        ):
            dsdir = ds.pathobj
            try:
                (dsdir / dandiset_metadata_file).unlink()
            except FileNotFoundError:
                pass
            metadata = dandiset.get("metadata", {})
            Dandiset(dsdir, allow_empty=True).update_metadata(metadata)
            ds.repo.add([dandiset_metadata_file])
            local_assets = set(dsdir.glob("*/*"))
            for a in assets:
                gid = a["girder"]["id"]
                dandi_hash = a.get("metadata", {}).get("sha256")
                bucket_url = self.get_file_bucket_url(gid)
                dest = dsdir / a["path"].lstrip("/")
                dest.parent.mkdir(parents=True, exist_ok=True)
                local_assets.discard(dest)
                deststr = str(dest.relative_to(dsdir))
                if not dest.exists():
                    to_update = True
                elif dandi_hash is not None:
                    to_update = dandi_hash != get_annex_hash(deststr)
                else:
                    stat = dest.stat()
                    to_update = (
                        stat.st_size != a["metadata"]["uploaded_size"]
                        or stat.st_mtime != a["metadata"]["uploaded_mtime"].timestamp()
                    )
                if to_update:
                    src = self.assetstore_path / urlparse(bucket_url).path.lstrip("/")
                    if src.exists():
                        print(src, "->", dest)
                        try:
                            self.mklink(src, dest)
                        except Exception:
                            if self.ignore_errors:
                                continue
                            else:
                                raise
                    else:
                        ds.download_url(urls=bucket_url, path=deststr)
                    ds.repo.add([deststr])
                if dandi_hash is not None:
                    annex_key = get_annex_hash(deststr)
                    if dandi_hash != annex_key:
                        raise RuntimeError(
                            f"Hash mismatch for {deststr.relative_to(self.target_path)}!"
                            f"  Dandi reports {dandi_hash},"
                            f" datalad reports {annex_key}"
                        )
                ds.repo.add_url_to_file(deststr, bucket_url)
            for a in local_assets:
                ds.repo.remove([str(a.relative_to(dsdir))])
        ds.save(message="Ran backups2datalad.py")

    @staticmethod
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

    def get_file_bucket_url(self, girder_id):
        r = (self.session or requests).head(
            f"https://girder.dandiarchive.org/api/v1/file/{girder_id}/download"
        )
        r.raise_for_status()
        return r.headers["Location"]

    @staticmethod
    def mklink(src, dest):
        subprocess.run(
            [
                "cp",
                "-L",
                "--reflink=always",
                "--remove-destination",
                str(src),
                str(dest),
            ],
            check=True,
        )


if __name__ == "__main__":
    main()
