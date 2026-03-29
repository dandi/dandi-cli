#!/usr/bin/env python3
"""Regenerate uberon_brain_structures.json from the UBERON OBO file.

Run: python -m dandi.data.generate_uberon_structures

Downloads the UBERON OBO file, parses it without any library dependency,
extracts brain/nervous system descendants, and writes a compact JSON file.
"""

from __future__ import annotations

from collections import defaultdict
import json
from pathlib import Path
import re

import requests

# Root terms whose descendants (via is_a and part_of) we collect.
_ROOT_IDS = frozenset({"UBERON:0001016", "UBERON:0000955"})  # nervous system, brain


def _parse_obo_terms(text: str) -> list[dict]:  # pragma: no cover
    """Parse [Term] stanzas from raw OBO text."""
    terms: list[dict] = []
    in_term = False
    current: dict = {}

    for line in text.splitlines():
        line = line.strip()
        if line == "[Term]":
            if current.get("id"):
                terms.append(current)
            current = {"id": "", "name": "", "synonyms": [], "parents": []}
            in_term = True
            continue
        if line.startswith("[") and line.endswith("]"):
            # Another stanza type (e.g. [Typedef])
            if current.get("id"):
                terms.append(current)
            current = {}
            in_term = False
            continue
        if not in_term:
            continue
        if not line or line.startswith("!"):
            continue

        if line == "is_obsolete: true":
            current["id"] = ""  # mark for skipping
            continue
        if line.startswith("id: "):
            current["id"] = line[4:]
        elif line.startswith("name: "):
            current["name"] = line[6:]
        elif line.startswith("is_a: "):
            parent_id = line[6:].split("!")[0].strip()
            if parent_id.startswith("UBERON:"):
                current["parents"].append(parent_id)
        elif line.startswith("relationship: part_of "):
            parent_id = line[len("relationship: part_of ") :].split("!")[0].strip()
            if parent_id.startswith("UBERON:"):
                current["parents"].append(parent_id)
        elif line.startswith("synonym: "):
            m = re.match(r'synonym:\s+"(.+?)"\s+(EXACT|RELATED|NARROW|BROAD)', line)
            if m:
                current["synonyms"].append({"text": m.group(1), "scope": m.group(2)})

    if current.get("id"):
        terms.append(current)
    return terms


def _collect_descendants(
    terms: list[dict], root_ids: frozenset[str]
) -> set[str]:  # pragma: no cover
    """BFS from root_ids through children (reverse of is_a/part_of) edges."""
    children: dict[str, list[str]] = defaultdict(list)
    for t in terms:
        for parent in t["parents"]:
            children[parent].append(t["id"])

    visited: set[str] = set()
    queue = list(root_ids)
    while queue:
        node = queue.pop()
        if node in visited:
            continue
        visited.add(node)
        queue.extend(children.get(node, []))
    return visited


def main() -> None:  # pragma: no cover
    url = "http://purl.obolibrary.org/obo/uberon.obo"
    print(f"Downloading {url} ...")
    resp = requests.get(url, timeout=120)
    resp.raise_for_status()
    print(f"Downloaded {len(resp.text)} bytes, parsing ...")

    all_terms = _parse_obo_terms(resp.text)
    print(f"Parsed {len(all_terms)} terms")

    # Filter to UBERON terms only (skip cross-ontology references)
    uberon_terms = [t for t in all_terms if t["id"].startswith("UBERON:")]
    print(f"UBERON terms: {len(uberon_terms)}")

    descendant_ids = _collect_descendants(uberon_terms, _ROOT_IDS)
    print(f"Nervous system descendants (including roots): {len(descendant_ids)}")

    structures: list[dict] = []
    for t in uberon_terms:
        if t["id"] not in descendant_ids:
            continue
        numeric_id = t["id"].replace("UBERON:", "")
        entry: dict = {"id": numeric_id, "name": t["name"]}
        if t["synonyms"]:
            # Compact format: [text, scope_letter] to keep file under 500KB
            entry["synonyms"] = [
                [syn["text"], syn["scope"][0]] for syn in t["synonyms"]
            ]
        structures.append(entry)

    structures.sort(key=lambda s: s["id"])
    out_path = Path(__file__).with_name("uberon_brain_structures.json")
    with open(out_path, "w") as f:
        json.dump(structures, f, separators=(",", ":"))
        f.write("\n")
    print(f"Wrote {len(structures)} structures to {out_path}")


if __name__ == "__main__":  # pragma: no cover
    main()
