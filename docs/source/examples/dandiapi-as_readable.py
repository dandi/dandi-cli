from dandi.dandiapi import DandiAPIClient

dandiset_id = "000006"  # ephys dataset from the Svoboda Lab
filepath = "sub-anm372795/sub-anm372795_ses-20170718.nwb"  # 450 kB file

with DandiAPIClient() as client:
    asset = client.get_dandiset(dandiset_id, "draft").get_asset_by_path(filepath)
    # https://dandi.readthedocs.io/en/latest/modref/dandiapi.html#dandi.dandiapi.BaseRemoteBlobAsset.as_readable
    # provides file-like object which uses fsspec to provide sparse access to content
    # of the file on S3:
    with asset.as_readable().open() as f:
        print(f.read(4))
        f.seek(100)
        print(f.read(4))
