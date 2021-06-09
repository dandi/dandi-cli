"""
Command line interface for DANDI client

TODO:
- consider placing common option definitions into options.py submodule.
  pipenv is a nice example although common command definitions are somewhat
  too cubmersome.  yoh thinks he saw a bit more lightweight somewhere.
  e.g. girder-client
"""

try:
    # A trick found on https://github.com/h5py/h5py/issues/1079#issuecomment-567081386
    # to avoid some weird behavior on Yarik's laptop where MPI fails to initialize
    # and that takes h5py additional 5 seconds to import
    import mpi4py

    mpi4py.rc(initialize=False)
except Exception:
    pass
