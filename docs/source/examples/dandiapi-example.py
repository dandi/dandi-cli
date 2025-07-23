import json

from dandi.dandiapi import DandiAPIClient

with DandiAPIClient.for_dandi_instance("dandi") as client:
    for dandiset in client.get_dandisets():
        # Note: for demo purposes we go only through a few dandisets, and skip all others
        # so comment out/remove this condition if you would like to go through all.
        if not (35 < int(dandiset.identifier) < 40):
            print(f"For demo purposes skipping {dandiset}")
            continue
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
                # Note: for demonstration purposes we stop at a single asset found
                print(
                    f"Was found in dandiset {dandiset}. For demo purposes skipping other assets"
                )
                break
