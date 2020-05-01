import os.path as op
import re
import requests

from . import girder, get_logger
from .consts import dandiset_metadata_file, known_instances
from .dandiset import Dandiset
from .exceptions import FailedToConnectError, NotFoundError, UnknownURLError
from .utils import flatten, flattened, Parallel, delayed

lgr = get_logger()


class _dandi_url_parser:
    # Defining as a class with all the attributes to not leak all the variables etc
    # into module space, and later we might end up with classes for those anyways
    id_regex = "[a-f0-9]{24}"
    id_grp = f"(?P<id>{id_regex})"
    server_grp = "(?P<server>(?P<protocol>https?)://(?P<hostname>[^/]+)/)"
    known_urls = {
        # Those we first redirect and then handle the redirected URL
        # TODO: Later should better conform to our API, so we could allow
        #       for not only "dandiarchive.org" URLs
        "https?://dandiarchive.org/.*": {"handle_redirect": True},
        "https?://[^/]*dandiarchive-org.netlify.app/.*": {"map_instance": "dandi"},
        # Girder-inflicted urls to folders etc based on the IDs
        # For those we will completely ignore domain - it will be "handled"
        f"{server_grp}#.*/(?P<asset_type>folder|collection|dandiset-meta)/{id_grp}$": {},
        # Nothing special
        # Multiple items selected - will need custom handling of 'multiitem'
        f"{server_grp}#/folder/{id_regex}/selected(?P<multiitem>(/item\\+{id_grp})+)$": {},
        # Direct girder urls to items
        f"{server_grp}api/v1/(?P<asset_type>item)/{id_grp}/download$": {},
    }
    # We might need to remap some assert_types
    map_asset_types = {"dandiset-meta": "folder"}
    # And lets create our mapping into girder instances from known_instances:
    map_to_girder = {}
    for girder, *_ in known_instances.values():
        for h in _:
            if h:
                map_to_girder[h] = girder

    @classmethod
    def parse(cls, url, map_instance=True):
        """Parse url like and return server (address), asset_id and/or directory

        Example URLs (as of 20200310):
        - User public: (Users -> bendichter/Public/Tolias2020)
          [seems to be visible only if logged in]
          https://gui.dandiarchive.org/#/folder/5e5593cc1a343161ff7c5a92
          https://girder.dandiarchive.org/#user/5da4b8fe51c340795cb18fd0/folder/5e5593cc1a343161ff7c5a92
        - Collection top level (Collections -> yarik):
          https://gui.dandiarchive.org/#/collection/5daa5ca7e3489855a3027682
          https://girder.dandiarchive.org/#collection/5daa5ca7e3489855a3027682
        - Collections: (Collections -> yarik/svoboda)
          https://gui.dandiarchive.org/#/folder/5dab0830f377535c7d96c2b4
          https://girder.dandiarchive.org/#collection/5daa5ca7e3489855a3027682/folder/5dab0830f377535c7d96c2b4
        - Dataset landing page metadata
          https://gui.dandiarchive.org/#/dandiset-meta/5e6d5c6976569eb93f451e4f

        Individual and multiple files:
          - dandi???
          - girder -- we don't support:
            https://girder.dandiarchive.org/api/v1/item/5dab0972f377535c7d96c392/download
          - gui.: support single or multiple
            # if there is a selection, we could get multiple items
            https://gui.dandiarchive.org/#/folder/5e60c14f81bc3e47d94aa012/selected/item+5e60c19381bc3e47d94aa014

        Multiple selected files + folders -- we do not support ATM, then further
        RFing would be due, probably making this into a generator or returning a
        list of entries.

        "Features":

        - supports DANDI naming, such as https://dandiarchive.org/dandiset/000001
          Since currently redirects, it just resorts to redirect if url lacks #.
          TODO: make more efficient, .head instead of .get or some other way to avoid
          full download_file.
        - uses some of `known_instance`s to map some urls, e.g. from
          gui.dandiarchive.org ones into girder.

        Returns
        -------
        server, asset_type, asset_id
          asset_type is either asset_id or folder ATM. asset_id might be a list
          in case of multiple files

        """
        lgr.debug("Parsing url %s", url)

        # Loop through known url regexes and stop as soon as one is matching
        match = None
        for regex, settings in cls.known_urls.items():
            match = re.match(regex, url)
            if not match:
                continue
            if settings.get("handle_redirect", False):
                new_url = cls.follow_redirect(url)
                if new_url != url:
                    return cls.parse(new_url)
                # We used to issue warning in such cases, but may be it got implemented
                # now via reverse proxy and we had added a new regex? let's just
                # continue with a debug msg
                lgr.debug("Redirection did not happen for %s", url)
            elif settings.get("map_instance"):
                if map_instance:
                    server, *_ = cls.parse(url, map_instance=False)
                    if settings["map_instance"] not in known_instances:
                        raise ValueError(
                            "Unknown instance {}. Known are: {}".format(
                                settings["map_instance"], ", ".join(known_instances)
                            )
                        )
                    return (known_instances[settings["map_instance"]].girder,) + tuple(
                        _
                    )
                continue  # in this run we ignore an match further
            else:
                break

        if not match:
            known_regexes = "\n - ".join([""] + list(cls.known_urls))
            # TODO: may be make use of etelemetry and report if newer client
            # which might know is available?
            raise UnknownURLError(
                f"We do not know how to map URL {url} to girder.\n"
                f"Regular expressions for known setups:"
                f"{known_regexes}"
            )

        groups = match.groupdict()
        girder_server = cls.map_to_girder.get(
            groups["server"].rstrip("/"), groups["server"]
        )
        if not girder_server.endswith("/"):
            girder_server += "/"  # we expected '/' to be there so let it be

        if "multiitem" not in groups:
            # we must be all set
            asset_ids = [groups["id"]]
            asset_type = groups["asset_type"]
            asset_type = cls.map_asset_types.get(asset_type, asset_type)
        else:
            # we need to split/parse them and return a list
            asset_ids = [i.split("+")[1] for i in groups["multiitem"].split("/") if i]
            asset_type = "item"
        ret = girder_server, asset_type, asset_ids
        lgr.debug("Parsed into %s", ret)
        return ret

    @staticmethod
    def follow_redirect(url):
        # assume that it was a dandi notation, let's try to follow redirects
        # TODO: make .head work instead of .get on the redirector
        r = requests.get(url, allow_redirects=True)
        if r.status_code == 404:
            raise NotFoundError(url)
        elif r.status_code != 200:
            raise FailedToConnectError(
                f"Response for getting {url} to redirect returned " f"{r.status_code}."
            )
        elif r.url != url:
            return r.url
        return url


# convenience binding
parse_dandi_url = _dandi_url_parser.parse


def download(
    urls,
    output_dir,
    existing="error",
    jobs=6,
    develop_debug=False,
    authenticate=False,  # Seems to work just fine for public stuff
    recursive=True,
):
    """Download a file or entire folder from DANDI"""
    urls = flattened([urls])
    if len(urls) > 1:
        raise NotImplementedError("multiple URLs not supported")
    if not urls:
        # if no paths provided etc, we will download dandiset path
        # we are at, BUT since we are not git -- we do not even know
        # on which instance it exists!  Thus ATM we would do nothing but crash
        raise NotImplementedError("No URLs were provided.  Cannot download anything")
    url = urls[0]
    girder_server_url, asset_type, asset_id = parse_dandi_url(url)

    # We could later try to "dandi_authenticate" if run into permission issues.
    # May be it could be not just boolean but the "id" to be used?
    client = girder.get_client(
        girder_server_url,
        authenticate=authenticate,
        progressbars=True,  # TODO: redo all this
    )

    lgr.info(f"Downloading {asset_type} with id {asset_id} from {girder_server_url}")

    # there might be multiple asset_ids, e.g. if multiple files were selected etc,
    # so we will traverse all of them
    files = flatten(
        _get_asset_files(
            asset_id_, asset_type, output_dir, client, authenticate, existing, recursive
        )
        for asset_id_ in set(flattened([asset_id]))
    )

    Parallel(n_jobs=jobs, backend="threading")(
        delayed(client.download_file)(
            file["id"],
            op.join(output_dir, file["path"]),
            existing=existing,
            attrs=file["attrs"],
        )
        for file in files
    )


def _get_asset_files(
    asset_id, asset_type, output_dir, client, authenticate, existing, recursive
):
    # asset_rec = client.getResource(asset_type, asset_id)
    # lgr.info("Working with asset %s", str(asset_rec))
    # In principle Girder's client already has ability to download any
    # resource (collection/folder/item/file).  But it seems that "mending" it
    # with custom handling (e.g. later adding filtering to skip some files,
    # or add our own behavior on what to do when files exist locally, etc) would
    # not be easy.  So we will reimplement as a two step (kinda) procedure.
    # Return a generator which would be traversing girder and yield records
    # of encountered resources.
    # TODO later:  may be look into making it async
    # First we access top level records just to sense what we are working with
    top_entities = None
    while True:
        try:
            # this one should enhance them with "fullpath"
            top_entities = list(
                client.traverse_asset(asset_id, asset_type, recursive=False)
            )
            break
        except girder.gcl.HttpError as exc:
            if not authenticate and girder.is_access_denied(exc):
                lgr.warning("unauthenticated access denied, let's authenticate")
                client.dandi_authenticate()
                continue
            raise
    entity_type = list(set(e["type"] for e in top_entities))
    if len(entity_type) > 1:
        raise ValueError(
            f"Please point to a single type of entity - either dandiset(s),"
            f" folder(s) or file(s).  Got: {entity_type}"
        )
    entity_type = entity_type[0]
    if entity_type in ("dandiset", "folder"):
        # redo recursively
        lgr.info(
            "Traversing remote %ss (%s) recursively and downloading them " "locally",
            entity_type,
            ", ".join(e["name"] for e in top_entities),
        )
        entities = client.traverse_asset(asset_id, asset_type, recursive=recursive)
        # TODO: special handling for a dandiset -- we might need to
        #  generate dandiset.yaml out of the metadata record
        # we care only about files ATM
        files = (e for e in entities if e["type"] == "file")
    elif entity_type == "file":
        files = top_entities
    else:
        raise ValueError(f"Unexpected entity type {entity_type}")
    if entity_type == "dandiset":
        for e in top_entities:
            dandiset_path = op.join(output_dir, e["path"])
            dandiset_yaml = op.join(dandiset_path, dandiset_metadata_file)
            lgr.info(
                f"Updating {dandiset_metadata_file} from obtained dandiset " f"metadata"
            )
            if op.lexists(dandiset_yaml):
                if existing != "overwrite":
                    lgr.info(
                        f"{dandiset_yaml} already exists.  Set 'existing' "
                        f"to overwrite if you want it to be redownloaded. "
                        f"Skipping"
                    )
                    continue
            dandiset = Dandiset(dandiset_path, allow_empty=True)
            dandiset.path_obj.mkdir(exist_ok=True)  # exist_ok in case of parallel race
            dandiset.update_metadata(e.get("metadata", {}).get("dandiset", {}))
    return files
