import json

from lincbrain.dandiapi import DandiAPIClient

with DandiAPIClient.for_dandi_instance("dandi") as client:
    for dandiset in client.get_dandisets():
        if dandiset.most_recent_published_version is None:
            continue
        latest_dandiset = dandiset.for_version(dandiset.most_recent_published_version)
        for asset in latest_dandiset.get_assets():
            metadata = asset.get_metadata()
            if any(
                mtt is not None and "two-photon" in mtt.name
                for mtt in (metadata.measurementTechnique or [])
            ):
                print(json.dumps(metadata.json_dict(), indent=4))
                # Can be used to also download the asset:
                # asset.download(pathlib.Path(dandiset.identifier, asset.path))
