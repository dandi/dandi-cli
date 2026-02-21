#!/usr/bin/env python3
"""Regenerate allen_ccf_structures.json from Allen Brain Map API.

Run: python -m dandi.data.generate_allen_structures
"""

from __future__ import annotations

import json
from pathlib import Path

import requests


def _flatten(node: dict, out: list[dict]) -> None:
    out.append({"id": node["id"], "acronym": node["acronym"], "name": node["name"]})
    for child in node.get("children", []):
        _flatten(child, out)


def main() -> None:
    url = "http://api.brain-map.org/api/v2/structure_graph_download/1.json"
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    structures: list[dict] = []
    root = data["msg"][0]
    _flatten(root, structures)
    structures.sort(key=lambda s: s["id"])
    out_path = Path(__file__).with_name("allen_ccf_structures.json")
    with open(out_path, "w") as f:
        json.dump(structures, f, separators=(",", ":"))
    print(f"Wrote {len(structures)} structures to {out_path}")


if __name__ == "__main__":
    main()
