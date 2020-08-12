import os
import os.path as op

from . import get_logger
from . import girder
from .consts import dandiset_metadata_file, routes
from .dandiset import Dandiset
from .utils import get_instance

lgr = get_logger()


def register(name, description, dandiset_path=None, dandi_instance="dandi"):
    dandi_instance = get_instance(dandi_instance)
    if not dandiset_path and op.exists(dandiset_metadata_file):
        dandiset = Dandiset.find(os.getcwd())
        if dandiset:
            if "identifier" in dandiset.metadata:
                lgr.warning(
                    "Running 'register' while in a dandiset at %s.  We will "
                    "not generate %s",
                    dandiset,
                    dandiset_metadata_file,
                )
            else:
                dandiset_path = dandiset.path
                lgr.info(
                    "We will populate %s of the %s dandiset",
                    dandiset_metadata_file,
                    dandiset.path,
                )

    client = girder.get_client(dandi_instance.girder)
    dandiset = client.register_dandiset(name, description)

    url = routes.dandiset_draft.format(**locals())

    lgr.info(f"Registered dandiset at {url}. Please visit and adjust metadata.")
    if dandiset_path:
        ds = Dandiset(dandiset_path, allow_empty=True)
        ds.update_metadata(dandiset)
        return None
    else:
        lgr.info(
            "No dandiset path was provided and no dandiset detected in the path."
            " Here is a record for %s",
            dandiset_metadata_file,
        )
        return Dandiset.get_dandiset_record(dandiset)
