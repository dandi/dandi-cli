"""
ATM primarily a sandbox for some functionality for  dandi organize
"""


def get_pynwb_ndtypes_map():
    """Return a dict to map neuro datatypes known to pynwb to "modalities"

    It is an ugly hack, largely to check feasibility.
    It would base modality on the filename within pynwb providing that neural
    data type
    """
    import pynwb
    import inspect

    ndtypes = {}

    # They import all submods within __init__
    for a, v in pynwb.__dict__.items():
        if not (inspect.ismodule(v) and v.__name__.startswith("pynwb.")):
            continue
        for a_, v_ in v.__dict__.items():
            # now inspect all things within and get neural datatypes
            if inspect.isclass(v_) and issubclass(v_, pynwb.core.NWBMixin):
                ndtype = v_.__name__

                v_split = v_.__module__.split(".")
                if len(v_split) != 2:
                    print("Skipping %s coming from %s" % v_, v_.__module__)
                    continue
                modality = v_split[1]  # so smth like ecephys

                if ndtype in ndtypes:
                    if ndtypes[ndtype] == modality:
                        continue  # all good, just already known
                    raise RuntimeError(
                        "We already have %s pointing to %s, but now got %s"
                        % (ndtype, ndtypes[ndtype], modality)
                    )
                ndtypes[ndtype] = modality

    return ndtypes


### PASTE YOUR STUFF HERE MICHAEL


if __name__ == "__main__":
    print(get_pynwb_ndtypes_map())
