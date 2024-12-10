from dataclasses import asdict
import sys

import click
import ruamel.yaml

from .base import map_to_click_exceptions
from ..consts import known_instances


@click.command()
@map_to_click_exceptions
def instances():
    """List known DANDI instances that the CLI can interact with"""
    yaml = ruamel.yaml.YAML(typ="safe")
    yaml.default_flow_style = False
    instances = {}
    for inst in known_instances.values():
        data = asdict(inst)
        data.pop("name")
        instances[inst.name] = data
    yaml.dump(instances, sys.stdout)
