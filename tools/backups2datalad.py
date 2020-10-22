#!/usr/bin/env python

__requires__ = ["boto3", "click", "dandi", "datalad", "requests"]

"""
IMPORTANT NOTE ABOUT GIT CREDENTIALS

This script uses `datalad create-sibling-github` to create GitHub repositories
that are then pushed to GitHub.  The first step requires either GitHub user
credentials stored in the system's credentials store or else a GitHub OAuth
token stored in the global Git config under `hub.oauthtoken`.  In addition,
pushing to the GitHub remotes happens over SSH, so an SSH key that has been
registered with a GitHub account is needed for the second step.

TODOs:
    - move to dandisets repo
    - all logs should go under .git/dandi/logs -- do not "save" them at all
    - make work with released datalad (so return back special remote setup helpers)
    - use ssh only for "pushurl" and regular "https" for url for github sibling

Maybes:
    - do not push in here, push will be outside upon success of the entire hierarchy

Later TODOs

- become aware of superdataset, add new subdatasets if created and ran
  not for a specific subdataset
- parallelize across datasets or may be better files (would that be possible within 
  dataset?) using DataLad's #5022 ConsumerProducer?

"""

raise NotImplementedError("see above TODOs")

from collections import deque
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime
import logging
import os
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import urlparse, urlunparse

import boto3
from botocore import UNSIGNED
from botocore.client import Config
import click
from dandi import girder
from dandi.consts import dandiset_metadata_file
from dandi.dandiarchive import navigate_url
from dandi.dandiset import Dandiset
from dandi.support.digests import Digester
from dandi.utils import get_instance
import datalad
from datalad.api import Dataset
from datalad.support.json_py import dump
import requests

log = logging.getLogger(Path(sys.argv[0]).name)


@click.command()
@click.option("--backup-remote", help="Name of the rclone remote to push to")
@click.option("--gh-org", help="GitHub organization to create repositories under")
@click.option("-i", "--ignore-errors", is_flag=True)
@click.option(
    "-J",
    "--jobs",
    type=int,
    default=10,
    help="How many parallel jobs to use when pushing",
    show_default=True,
)
@click.option(
    "--re-filter", help="Only consider assets matching the given regex", metavar="REGEX"
)
@click.argument("assetstore", type=click.Path(exists=True, file_okay=False))
@click.argument("target", type=click.Path(file_okay=False))
@click.argument("dandisets", nargs=-1)
def main(
    assetstore, target, dandisets, ignore_errors, gh_org, re_filter, backup_remote, jobs
):
    logging.basicConfig(
        format="%(asctime)s [%(levelname)-8s] %(name)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
        level=logging.INFO,
        force=True,  # Override dandi's settings
    )
    DatasetInstantiator(
        assetstore_path=Path(assetstore),
        target_path=Path(target),
        ignore_errors=ignore_errors,
        gh_org=gh_org,
        re_filter=re_filter and re.compile(re_filter),
        backup_remote=backup_remote,
        jobs=jobs,
    ).run(dandisets)


class DatasetInstantiator:
    def __init__(
        self,
        assetstore_path: Path,
        target_path: Path,
        ignore_errors=False,
        gh_org=None,
        re_filter=None,
        backup_remote=None,
        jobs=10,
    ):
        self.assetstore_path = assetstore_path
        self.target_path = target_path
        self.ignore_errors = ignore_errors
        self.gh_org = gh_org
        self.re_filter = re_filter
        self.backup_remote = backup_remote
        self.jobs = jobs
        self.session = None
        self._s3client = None

    def run(self, dandisets=()):
        if not (self.assetstore_path / "girder-assetstore").exists():
            raise RuntimeError(
                "Given assetstore path does not contain girder-assetstore folder"
            )
        self.target_path.mkdir(parents=True, exist_ok=True)
        datalad.cfg.set("datalad.repo.backend", "SHA256E", where="override")
        with requests.Session() as self.session:
            for did in dandisets or self.get_dandiset_ids():
                dsdir = self.target_path / did
                log.info("Syncing Dandiset %s", did)
                ds = Dataset(str(dsdir))
                if not ds.is_installed():
                    log.info("Creating Datalad dataset")
                    ds.create(cfg_proc="text2git")
                    if self.backup_remote is not None:
                        ds.repo.init_remote(
                            self.backup_remote,
                            [],
                            type="rclone",
                            external=True,
                            config={
                                "chunk": "1GB",
                                "target": self.backup_remote,  # I made them matching
                                "prefix": "dandi-dandisets/annexstore",
                                "embedcreds": "no",
                                "uuid": "727f466f-60c3-4778-90b2-b2332856c2f8"
                                # shared, initialized in 000003
                            },
                        )
                        ds.repo._run_annex_command(
                            "untrust", annex_options=[self.backup_remote]
                        )
                        ds.repo.set_preferred_content(
                            "wanted",
                            "(not metadata=distribution-restrictions=*)",
                            remote=self.backup_remote,
                        )

                if self.sync_dataset(did, ds):
                    log.info("Creating GitHub sibling for %s", ds.pathobj.name)
                    ds.create_sibling_github(
                        reponame=ds.pathobj.name,
                        existing="skip",
                        name="github",
                        access_protocol="ssh",
                        github_organization=self.gh_org,
                        publish_depends=self.backup_remote,
                    )
                    ds.config.set("branch.master.remote", "github", where="local")
                    log.info("Pushing to sibling")
                    ds.push(to="github", jobs=self.jobs)

    def sync_dataset(self, dandiset_id, ds):
        # Returns true if any changes were committed to the repository
        if ds.repo.dirty:
            raise RuntimeError("Dirty repository; clean or save before running")
        digester = Digester(digests=["sha256"])
        hash_mem = {}

        def get_annex_hash(filepath):
            if filepath not in hash_mem:
                relpath = str(filepath.relative_to(dsdir))
                if ds.repo.is_under_annex(relpath, batch=True):
                    hash_mem[filepath] = (
                        ds.repo.get_file_key(relpath).split("-")[-1].partition(".")[0]
                    )
                else:
                    hash_mem[filepath] = digester(filepath)["sha256"]
            return hash_mem[filepath]

        dsdir = ds.pathobj
        latest_mtime = None
        added = 0
        updated = 0
        deleted = 0

        with dandi_logging(dsdir) as logfile, navigate_url(
            f"https://dandiarchive.org/dandiset/{dandiset_id}/draft"
        ) as (_, dandiset, assets):
            log.info("Updating metadata file")
            try:
                (dsdir / dandiset_metadata_file).unlink()
            except FileNotFoundError:
                pass
            metadata = dandiset.get("metadata", {})
            Dandiset(dsdir, allow_empty=True).update_metadata(metadata)
            ds.repo.add([dandiset_metadata_file])
            local_assets = set(dataset_files(dsdir))
            local_assets.discard(dsdir / dandiset_metadata_file)
            asset_metadata = []
            for a in assets:
                dest = dsdir / a["path"].lstrip("/")
                deststr = str(dest.relative_to(dsdir))
                local_assets.discard(dest)
                am = deepcopy(a)
                am["modified"] = str(am["modified"])
                asset_metadata.append(am)
                if self.re_filter and not self.re_filter.search(a["path"]):
                    log.info("Skipping asset %s", a["path"])
                    continue
                log.info("Syncing asset %s", a["path"])
                gid = a["girder"]["id"]
                dandi_hash = a.get("sha256")
                if dandi_hash is None:
                    log.warning("Asset metadata does not include sha256 hash")
                mtime = a["modified"]  # type: datetime
                bucket_url = self.get_file_bucket_url(gid)
                dest.parent.mkdir(parents=True, exist_ok=True)
                if not dest.exists():
                    log.info("Asset not in dataset; will copy")
                    to_update = True
                    added += 1
                elif dandi_hash is not None:
                    if dandi_hash == get_annex_hash(dest):
                        log.info(
                            "Asset in dataset, and hash shows no modification; will not update"
                        )
                        to_update = False
                    else:
                        log.info(
                            "Asset in dataset, and hash shows modification; will update"
                        )
                        to_update = True
                        updated += 1
                else:
                    sz = dest.stat().st_size
                    if sz == a["attrs"]["size"]:
                        log.info(
                            "Asset in dataset, hash not available,"
                            " and size is unchanged; will not update"
                        )
                        to_update = False
                    else:
                        raise RuntimeError(
                            f"Size mismatch for {dest.relative_to(self.target_path)}!"
                            f"  Dandiarchive reports {a['attrs']['size']},"
                            f" local asset is size {sz}"
                        )
                if to_update:
                    src = self.assetstore_path / urlparse(bucket_url).path.lstrip("/")
                    if src.exists():
                        try:
                            self.mklink(src, dest)
                        except Exception:
                            if self.ignore_errors:
                                log.warning("cp command failed; ignoring")
                                continue
                            else:
                                raise
                        log.info("Adding asset to dataset")
                        ds.repo.add([deststr])
                        if ds.repo.is_under_annex(deststr, batch=True):
                            log.info("Adding URL %s to asset", bucket_url)
                            ds.repo.add_url_to_file(deststr, bucket_url, batch=True)
                        else:
                            log.info("File is not managed by git annex; not adding URL")
                    else:
                        log.info(
                            "Asset not found in assetstore; downloading from %s",
                            bucket_url,
                        )
                        ds.download_url(urls=bucket_url, path=deststr)
                    if latest_mtime is None or mtime > latest_mtime:
                        latest_mtime = mtime
                if dandi_hash is not None:
                    annex_key = get_annex_hash(dest)
                    if dandi_hash != annex_key:
                        raise RuntimeError(
                            f"Hash mismatch for {dest.relative_to(self.target_path)}!"
                            f"  Dandiarchive reports {dandi_hash},"
                            f" datalad reports {annex_key}"
                        )
            for a in local_assets:
                astr = str(a.relative_to(dsdir))
                if self.re_filter and not self.re_filter.search(astr):
                    continue
                log.info(
                    "Asset %s is in dataset but not in Dandiarchive; deleting", astr
                )
                ds.repo.remove([astr])
                deleted += 1
            dump(asset_metadata, dsdir / ".dandi" / "assets.json")
        if any(r["state"] != "clean" for r in ds.status()):
            log.info("Commiting changes")
            msgbody = ""
            if added:
                msgbody += f"{added} files added\n"
            if updated:
                msgbody += f"{updated} files updated\n"
            if deleted:
                msgbody += f"{deleted} files deleted\n"
            with custom_commit_date(latest_mtime):
                ds.save(message=f"Ran backups2datalad.py\n\n{msgbody}")
            return True
        else:
            log.info("No changes made to repository; deleting logfile")
            logfile.unlink()
            return False

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
        urlbits = urlparse(r.headers["Location"])
        s3meta = self.s3client.get_object(
            Bucket="dandiarchive", Key=urlbits.path.lstrip("/")
        )
        return urlunparse(urlbits._replace(query=f"versionId={s3meta['VersionId']}"))

    @property
    def s3client(self):
        if self._s3client is None:
            self._s3client = boto3.client(
                "s3", config=Config(signature_version=UNSIGNED)
            )
        return self._s3client

    @staticmethod
    def mklink(src, dest):
        log.info("cp %s -> %s", src, dest)
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


@contextmanager
def custom_commit_date(dt):
    if dt is not None:
        with envvar_set("GIT_AUTHOR_DATE", str(dt)):
            with envvar_set("GIT_COMMITTER_DATE", str(dt)):
                yield
    else:
        yield


@contextmanager
def envvar_set(name, value):
    oldvalue = os.environ.get(name)
    os.environ[name] = value
    try:
        yield
    finally:
        if oldvalue is not None:
            os.environ[name] = oldvalue
        else:
            del os.environ[name]


def dataset_files(dspath):
    files = deque(
        p
        for p in dspath.iterdir()
        if p.name not in (".dandi", ".datalad", ".git", ".gitattributes")
    )
    while files:
        p = files.popleft()
        if p.is_file():
            yield p
        elif p.is_dir():
            files.extend(p.iterdir())


@contextmanager
def dandi_logging(dandiset_path: Path):
    logdir = dandiset_path / ".dandi" / "logs"
    logdir.mkdir(exist_ok=True, parents=True)
    filename = "sync-{:%Y%m%d%H%M%SZ}-{}.log".format(datetime.utcnow(), os.getpid())
    logfile = logdir / filename
    handler = logging.FileHandler(logfile, encoding="utf-8")
    fmter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)-8s] %(name)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
    )
    handler.setFormatter(fmter)
    root = logging.getLogger()
    root.addHandler(handler)
    try:
        yield logfile
    except Exception:
        log.exception("Operation failed with exception:")
        raise
    finally:
        root.removeHandler(handler)


if __name__ == "__main__":
    main()
