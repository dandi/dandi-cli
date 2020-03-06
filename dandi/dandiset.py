"""Classes/utilities for support of a dandiset"""

import yaml
from pathlib import Path

from .consts import dandiset_metadata_file
from .utils import find_parent_directory_containing


class Dandiset(object):
    """A prototype class for all things dandiset
    """

    __slots__ = ["metadata", "path", "path_obj"]

    def __init__(self, path):
        self.path = str(path)
        self.path_obj = Path(path)
        if not (self.path_obj / dandiset_metadata_file).exists():
            raise ValueError(f"No dandiset at {path}")

        self.metadata = None
        self._load_metadata()

    @classmethod
    def find(cls, path):
        """Find a dandiset possibly pointing to a directory within it
        """
        dandiset_path = find_parent_directory_containing(dandiset_metadata_file, path)
        if dandiset_path:
            return cls(dandiset_path)
        return None

    def _load_metadata(self):
        with open(self.path_obj / dandiset_metadata_file) as f:
            # TODO it would cast 000001 if not explicitly string into
            # an int -- we should prevent it... probably with some custom loader
            self.metadata = yaml.safe_load(f)

    @property
    def identifier(self):
        return self.metadata["identifier"]
