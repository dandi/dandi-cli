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
        v_split = v.__name__.split(".")
        if len(v_split) != 2:
            print("Skipping %s" % v.__name__)
        modality = v_split[1]  # so smth like ecephys
        # now inspect all things within and get neural datatypes
        if issubclass(v, sdf):
            pass


### PASTE YOUR STUFF HERE MICHAEL


if __name__ == "__main__":
    get_pynwb_ndtypes_map()
