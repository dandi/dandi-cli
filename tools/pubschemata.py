from pathlib import Path
import sys
from dandi.models import AssetMeta, CommonModel, DandiMeta


def publish_model_schemata(releasedir):
    version = CommonModel.__fields__["schemaVersion"].default
    vdir = Path(releasedir, version)
    vdir.mkdir(exist_ok=True, parents=True)
    (vdir / "dandiset.json").write_text(DandiMeta.schema_json(indent=2))
    (vdir / "asset.json").write_text(AssetMeta.schema_json(indent=2))


if __name__ == "__main__":
    publish_model_schemata(sys.argv[1])
