"""Regenerate uberon_brain_structures.json from the UBERON OBO file.

Downloads the UBERON OBO file, parses it without any library dependency,
extracts brain/nervous system descendants, and writes the bundled JSON.

Can be run via::

    dandi service-scripts generate-uberon-structures
"""

from __future__ import annotations

from collections import defaultdict
import json
import logging
from pathlib import Path
import re

import requests

lgr = logging.getLogger(__name__)

# Root terms whose descendants (via is_a and part_of) we collect.
_ROOT_IDS = frozenset({"UBERON:0001016", "UBERON:0000955"})  # nervous system, brain

_OUTPUT_PATH = Path(__file__).with_name("uberon_brain_structures.json")


def _parse_obo_terms(text: str) -> list[dict]:
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
            if m := re.match(
                r'synonym:\s+"(.+?)"\s+(EXACT|RELATED|NARROW|BROAD)', line
            ):
                current["synonyms"].append({"text": m.group(1), "scope": m.group(2)})

    if current.get("id"):
        terms.append(current)
    return terms


def _collect_descendants(terms: list[dict], root_ids: frozenset[str]) -> set[str]:
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


def generate(output: Path = _OUTPUT_PATH) -> None:
    """Download UBERON OBO and write brain/nervous-system structures JSON."""
    url = "http://purl.obolibrary.org/obo/uberon.obo"
    lgr.info("Downloading %s ...", url)
    resp = requests.get(url, timeout=120)
    resp.raise_for_status()
    lgr.info("Downloaded %d bytes, parsing ...", len(resp.text))

    all_terms = _parse_obo_terms(resp.text)
    lgr.info("Parsed %d terms", len(all_terms))

    # Filter to UBERON terms only (skip cross-ontology references)
    uberon_terms = [t for t in all_terms if t["id"].startswith("UBERON:")]
    lgr.info("UBERON terms: %d", len(uberon_terms))

    descendant_ids = _collect_descendants(uberon_terms, _ROOT_IDS)
    lgr.info("Nervous system descendants (including roots): %d", len(descendant_ids))

    structures: list[dict] = []
    for t in uberon_terms:
        if t["id"] not in descendant_ids:
            continue
        numeric_id = t["id"].replace("UBERON:", "")
        entry: dict = {"id": numeric_id, "name": t["name"]}
        if t["synonyms"]:
            # Compact format: [text, scope_letter]
            entry["synonyms"] = [
                [syn["text"], syn["scope"][0]] for syn in t["synonyms"]
            ]
        structures.append(entry)

    structures.sort(key=lambda s: s["id"])
    with open(output, "w") as f:
        json.dump(structures, f, indent=1)
        f.write("\n")
    lgr.info("Wrote %d structures to %s", len(structures), output)
