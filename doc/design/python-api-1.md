Designs for an improved Python API
==================================

* New base classes:
    * `Dandiset`
        * `identifier: str`
        * `created: datetime`
        * `modified: datetime`
        * `version: Optional[Version]`
        * `get_all_assets() -> Iterator[Asset]`
        * `get_assets_under_path(path: str) -> Iterator[Asset]` — Returns all assets whose paths are either under the given folder or equal the given filepath
        * `get_asset_by_path(path: str) -> Optional[Asset]` — Finds the unique asset with the given exact path; returns `None` if no such asset
        * `get_metadata() -> DandiMeta`
   * `Asset`:
        * `path: str`
        * `sha256: str` — Should this only be on `RemoteAsset`?
        * `size: int`
        * `created: datetime` — Should this only be on `RemoteAsset`?
        * `modified: datetime` — Should this only be on `RemoteAsset`?
        * `get_metadata() -> BareAssetMeta`

* `dandi.dandiapi`:
    * Upon creating a new `RESTFullAPIClient` instance, a new session object should automatically be created and used for all of the client's requests; the `session()` method should thus be eliminated
        * If we need to support user-supplied session objects, those should be passed in to the constructor
    * It may or may not be a good idea for the client to be usable as a context manager that closes its session on exit.
        * Con: Closing the session would affect `RemoteDandiset` etc. instances for the client (see below), making them unusable.
    * Rename the `send_request()` method to `request()` to parallel `requests.Session.request()`
    * Rename the `parameters` argument to the HTTP methods to `params` to match `requests`
    * The `api_url` argument to `DandiAPIClient`'s constructor should default to the URL for the official Dandiarchive instance (which should also be available as a constant)
    * Give `DandiAPIClient` a classmethod `for_dandi_instance(cls, instance: Union[str, dandi_instance], token=None, authenticate=True)` (Rethink name) that takes either the name of a Dandi instance or an actual `dandi_instance`, fetches a token from the environment, keychain, and/or user if one is not given and `authenticate` is true, and returns a `DandiAPIClient` instance
    * Most interaction with API resources should be via new `RemoteDandiset`, `Version`, and `RemoteAsset` classes and their methods
        * These classes (except `Version`?) will all contain a private `_client` attribute referring back to the associated `DandiAPIClient` instance.
    * Changes to `DandiAPIClient` methods:
        * Add a `get_dandiset(dandiset_id: Union[str, RemoteDandiset], version_id=None) -> RemoteDandiset` method
            * **To discuss:** Should the default `version` be "draft" or the most recent version?  Either way, there should be another method that explicitly gets the other option.
            * **To discuss:** Should this take a `lazy=False` parameter that, if true, constructs a `RemoteDandiset` containing only an identifier, without making any requests at the time of creation?  This would allow calling a `RemoteDandiset`'s methods without having to make a request for the Dandiset's data beforehand.  If & when any non-identifiers attributes of a lazy `RemoteDandiset` are requested, a request is made at that point and the results cached.
        * Add a `get_all_dandisets() -> Iterator[RemoteDandiset]` method
            * **To discuss:** What should these objects' `Version`s be?
        * Retype `create_dandiset` to `create_dandiset(name: str, metadata: DandiMeta) -> RemoteDandiset`
        * Add a `register_dandiset(dirpath: Union[str, Path], name: str, description: str) -> LocalDandiset` method that, in addition to calling `create_dandiset()`, also creates a `dandiset.yaml` file in `dirpath`?
        * Add a `get_current_user() -> User` method
        * Add a `search_users(username: str) -> Iterator[User]` method
        * Add an `upload(dandiset: LocalDandiset, paths: Optional[List[str]] = None, show_progress=True, existing="refesh", validation="require") -> List[RemoteAsset]` method
            * Use this to replace the `upload()` function
            * The elements of `paths` are interpreted the same way as the argument to `get_assets_under_path()`
        * The remaining methods should be either deleted or made private.
        * **To bikeshed:** Should the Dandiset and version arguments to these methods be named `dandiset` & `version` or `dandiset_id` & `version_id`?
    * Where a method can take an ID as either a string or an object, it is permitted for the object to belong to a different client.

    * Attributes & methods of the `RemoteDandiset` class, a subclass of the new `Dandiset` base class, representing a combination of the API's dandiset and version resources:
        * `identifier: str`
        * `created: datetime`
        * `modified: datetime`
        * `version: Version`
        * `most_recent_version: Version` ?
        * `get_version(version_id: Union[str, Version]) -> Version` ?
        * `get_all_versions() -> Iterator[Version]`
        * `for_version(version_id: Union[str, Version]) -> RemoteDandiset`
            * When `version_id == "draft"`, this is the same as `for_draft_version()`
        * `for_draft_version() -> DraftDandiset`
        * `delete() -> None`
        * `get_users() -> Iterator[User]`
        * `set_users(users: List[User]) -> None`
            * Should this method also accept strings giving the usernames directly?
        * `get_metadata() -> DandiMeta`
        * `publish() -> Version` (Should this be moved to `DraftDandiset`?)
        * `get_all_assets() -> Iterator[RemoteAsset]`
        * `get_assets_under_path(path: str) -> Iterator[RemoteAsset]`
        * `get_asset_by_path(path: str) -> Optional[RemoteAsset]`
        * `get_asset_by_uuid(uuid: str) -> Optional[RemoteAsset]` — Returns `None` if the given asset does not exist
        * `download(target_dir: Union[str, Path], paths: Optional[List[str]] = None, show_progress=True, existing="error", get_metadata=True) -> ???`
            * Use this to replace the `download()` function?
            * The elements of `paths` are interpreted the same way as the argument to `get_assets_under_path()`
            * `get_metadata` controls whether to create a `dandiset.yaml` file; should it default to `False` when `paths` is not `None`?
            * TO DO: Add an argument for controlling whether to create a directory under `target_dir` with the same name as the Dandiset ID?

    * Methods of the `DraftDandiset` class (a subclass of `RemoteDandiset` used only for mutable draft versions):
        * `set_metadata(metadata: DandiMeta) -> DraftDandiset` — returns the new, modified object
        * Methods for uploading an individual asset:
            * `upload_file(filepath: Union[str, Path], metadata: BareAssetMeta, show_progress=True, existing="refesh", validation="require") -> RemoteAsset`
            * `iter_upload_file(filepath: Union[str, Path], metadata: BareAssetMeta, existing="refesh", validation="require") -> Iterator[UploadProgressDict]`
            * `upload_asset(asset: LocalAsset, show_progress=True, existing="refesh", validation="require") -> RemoteAsset` ?
            * `iter_upload_asset(asset: LocalAsset, existing="refesh", validation="require") -> Iterator[UploadProgressDict]` ?
        * Methods for uploading a directory/collection of assets:
            * `upload_assets(assets: Iterable[LocalAsset], show_progress=True, existing="refesh", validation="require") -> List[RemoteAsset]`

    * Attributes & methods of the `Version` class:
        * `identifier: str`
        * `created: datetime`
        * `modified: datetime`
        * `name: str`
        * `asset_count: int`
        * `size: int`

    * Attributes & methods of the `RemoteAsset` class (a subclass of `Asset`):
        * `uuid: str`
        * `path: str`
        * `sha256: str`
        * `size: int`
        * `created: datetime`
        * `modified: datetime`
        * `dandiset_id: str`
        * `version_id: str`
        * `get_metadata() -> RemoteAssetMeta`
        * `set_metadata(metadata: BareAssetMeta) -> RemoteAsset` — returns the new, modified object
        * `delete() -> None`
        * `download(filepath: str, show_progress=True, chunk_size=...) -> ???`
        * `iter_download(filepath: str, chunk_size=...) -> Iterator[DownloadProgressDict]`

    * Attributes of the `User` class:
        * `username: str`
        * `first_name: str`
        * `last_name: str`
        * `admin: bool`
        * **Note:** We should ask the dandi-api developers to make the `GET/PUT /dandisets/{dandiset__pk}/users/` endpoints return full user structures, not just ones with only `username` fields, so that instances of this class can be properly populated

    * The upload & download methods (or at least the ones for uploading/downloading single assets) come in pairs:
        * The basic methods simply upload/download everything, blocking until completion, and return either nothing or a summary of everything that was uploaded/downloaded
            * These methods have `show_progress=True` options for whether to display progress output using pyout or to remain silent
            * The upload methods return an `Asset` or collection of `Asset`s.  This can be implemented by having the final value yielded by the `iter_` upload function contain an `"asset"` field.
        * Each method also has an iterator variant (named with an "`iter_`" preffix) that can be used to iterate over values containing progress information compatible with pyout
            * These methods do not output anything (aside perhaps from logging)

    * An `UploadProgressDict` is a `dict` containing some number of the following keys:
        * `dandiset_id: str` — always present
        * `version_id: str` — always present
        * `path: str` — always present
        * `status: str`
        * `upload: float` — percentage of file uploaded (rename to "pct"?)
        * `current: int` — number of bytes uploaded
        * `message: str`
        * `size: int` — the total size of the file
        * `errors: int`
        * `asset: RemoteAsset` — yielded in the last `dict` of a successful upload
    * A `DownloadProgressDict` is a `dict` containing some number of the following keys:
        * `dandiset_id: str` — always present
        * `version_id: str` — always present
        * `path: str` — always present
        * `status: str`
        * `message: str`
        * `size: int` — the total size of the file
        * `done: int` — number of bytes downloaded (Rename to "current"?)
        * `done%: float` — percentage of bytes downloaded (Rename to "download"? or "pct"?)
        * `checksum: str` — `"differs"`, `"ok"`, or `"-"`

    * **To discuss:** Should methods that accept `DandiMeta` and `(Bare|Remote)AssetMeta` instances also accept raw `dict`s?  If so, should any validation be done on these `dict`s?

* `dandi.dandiset`: Expand the ability for `Dandiset` (renamed to `LocalDandiset` and made a subclass of the new `Dandiset` base class) to represent a Dandiset on disk:
    * `path: Path` (or `dandiset_path`?)
    * `set_metadata(metadata: DandiMeta) -> None` ?
    * `validate_metadata() -> None`
    * `validate_assets() -> ???` ?
    * Make `organize()` a method of this class?
    * Add methods for marking local files as belonging/not belonging to the Dandiset (without changing anything on disk)
        * `add_path(path: Union[str, Path], ext: Union[str, Iterable[str]] = ".nwb") -> None`
            * If `path` is a directory, all files with an extension in `ext` under it (without recursing into VCS directories) are added.
        * `remove_path(path: Union[str, Path]) -> None`
            * If `path` is a directory, all files under it are removed.
        * `add_path_glob(pattern: str) -> None`
            * Recursive globs (with `**`) are supported
            * Should this filter out VCS directories?
        * `remove_path_glob(pattern: str) -> None`
            * Recursive globs (with `**`) are supported
    * Give the constructor arguments for controlling the initial set of files to include in the Dandiset (default: all `*.nwb` files)
        - `ext: Union[str, Iterable[str]] = ".nwb"` ?
        - [something for disabling auto-registration of files on construction; `register_files=True`?]

    * `LocalDandiset` uses `LocalAsset`s, a subclass of the new `Asset` base class:
         * `local_path: Path` — the path of the asset on disk

* Miscellaneous changes:
    * Add a `DRAFT = "draft"` constant so that misspellings can be caught by static analysis
    * Rename all constants (or at least the public ones) to be all-uppercase
    * Rename the `dandi_instance` class to `DandiInstance`
    * Add a `get_resource_by_url(url: str) -> Union[Dandiset, Version, Asset]` function that takes anything `parse_dandi_url()` accepts and returns the corresponding resource object ?
        * Also add specializations like `get_dandiset_by_url(url: str) -> Dandiset` that error if the URL points to a resource of the wrong type?
    * Rename `nwb2asset()` to `extract_asset_metadata()`
        * If the function is not passed any file digest data, have it calculate the digest itself?
    * Add a `VERSION_ID_RGX` constant
    * Give `CommonModel` a `validate()` method that just does `type(self)(**self.dict())`
    * Add a `UserInputError` exception class subclassing `ValueError`, use it for all errors caused by bad user input, and make `map_to_click_exceptions` only remap it and nothing else to `click.UsageError`
    * Make the return value of `parse_dandi_url()` a structured class
    * Rename the `download()` function to `download_url()`?
    * Add a `process_uploads(Iterable[Iterator[UploadProgressDict]], show_progress=True) -> List[RemoteAsset]` function that takes a collection of upload iterators and consumes them in parallel, using pyout if `show_progress` is true
    * Add a `process_downloads(Iterable[Iterator[DownloadProgressDict]], show_progress=True) -> ???` function that takes a collection of download iterators and consumes them in parallel, using pyout if `show_progress` is true
