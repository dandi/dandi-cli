#!/usr/bin/env python3
"""
A Python script to extract extension specifications and versions from NWB files.
Supports both local files and remote URLs, and outputs statistics on extension usage.
"""

import argparse
from collections import defaultdict
from dataclasses import asdict, dataclass, field, is_dataclass
import json
import sys
from typing import Dict, List

import h5py
from nwbinspector.tools import get_s3_urls_and_dandi_paths
from packaging import version
from tqdm import tqdm

from dandi.dandiapi import DandiAPIClient

# For remote file access
try:
    import remfile

    REMOTE_ACCESS_AVAILABLE = True
except ImportError:
    REMOTE_ACCESS_AVAILABLE = False


@dataclass
class ExtensionStats:
    """Data class to store statistics about an NWB extension."""

    name: str
    total_count: int = 0
    versions: Dict[str, int] = field(default_factory=lambda: defaultdict(int))


class EnhancedJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if is_dataclass(obj):
            return asdict(obj)
        return super().default(obj)


def get_nwb_specifications(file_path: str, is_url: bool = False) -> Dict[str, str]:
    """
    Extract all specification names and versions from an NWB file.

    Args:
        file_path: URL to the NWB file
        is_url: Whether the file_path is a URL

    Returns:
        Dictionary containing the specification names and versions
    """
    specifications = {}

    try:
        if is_url:
            if not REMOTE_ACCESS_AVAILABLE:
                raise ImportError("remfile is required for remote file access")

            # Open remote file using remfile
            f = remfile.File(file_path)
            try:
                h5_file = h5py.File(f, "r")
                # Need to use a context manager for the h5py file
                with h5_file as h5f:
                    specifications = _extract_specifications(h5f)
            finally:
                f.close()
        else:
            # Local file
            with h5py.File(file_path, "r") as f:
                specifications = _extract_specifications(f)

    except Exception as e:
        print(f"Error processing file {file_path}: {str(e)}", file=sys.stderr)

    return specifications


def _extract_specifications(h5_file) -> Dict[str, str]:
    """Extract specifications from an opened h5py File object."""
    specifications = {}

    if "specifications" in h5_file:
        specs_group = h5_file["specifications"]
        if len(specs_group) > 0:
            for name in specs_group:
                extension_group = specs_group[name]
                if not isinstance(extension_group, h5py.Group):
                    continue

                try:
                    sorted_versions = sorted(extension_group, key=version.parse)
                    if len(sorted_versions) > 0:
                        # Use only the latest version
                        latest_version = sorted_versions[-1]
                        specifications[name] = latest_version
                except Exception as e:
                    print(
                        f"Error processing extension {name}: {str(e)}", file=sys.stderr
                    )

    return specifications


def analyze_extensions(
    file_paths: List[str], is_url: bool = False
) -> List[ExtensionStats]:
    """
    Analyze extensions across multiple NWB files.

    Args:
        file_paths: List of paths or URLs to NWB files
        is_url: Whether the file_paths are URLs

    Returns:
        List of ExtensionStats objects
    """
    # Dictionary to store extension statistics
    extension_stats = {}

    # Process each file
    for file_path in tqdm(file_paths, desc="Processing NWB files"):
        specifications = get_nwb_specifications(file_path, is_url)

        # Filter out core specifications that are not extensions
        extensions = {
            k: v
            for k, v in specifications.items()
            # if k not in ["core", "hdmf-common", "hdmf-experimental"]
        }

        # Update statistics
        for ext_name, ext_version in extensions.items():
            if ext_name not in extension_stats:
                extension_stats[ext_name] = ExtensionStats(name=ext_name)

            extension_stats[ext_name].total_count += 1
            extension_stats[ext_name].versions[ext_version] += 1

    # Convert to list for output
    return list(extension_stats.values())

def snapshot_result(result, output):
    out = json.dumps(result, indent=2, cls=EnhancedJSONEncoder)
    if output:
        with open(output, "w") as f:
            f.write(out)
    return out

def main():
    parser = argparse.ArgumentParser(description="Analyze NWB file extensions")

    # Input source group (mutually exclusive)
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("-f", "--files", nargs="+", help="Local NWB file path(s)")
    input_group.add_argument("-u", "--urls", nargs="+", help="URL(s) to NWB file(s)")
    input_group.add_argument(
        "-d",
        "--dandisets",
        default=None,
        nargs="*",
        help="Dandisets to work on. If none specified but option is given, will process all",
    )

    # Output options
    parser.add_argument(
        "-o", "--output", help="Output JSON file path (default: stdout)"
    )

    args = parser.parse_args()

    # Determine input source
    if args.dandisets is not None:
        if not args.dandisets:  # specified but none specifically
            client = DandiAPIClient()
            dandisets = list(client.get_dandisets())
            args.dandisets = [d.identifier for d in dandisets]
        print(f"Analyzing {len(args.dandisets)} dandisets", file=sys.stderr)
        result = {}
        for d in tqdm(args.dandisets):
            urls = get_s3_urls_and_dandi_paths(dandiset_id=d)
            nwb_urls = [url for url, path in urls.items() if path.endswith(".nwb")]
            result[d] = analyze_extensions(nwb_urls, True)
            snapshot_result(result, args.output)
    else:
        if args.files:
            file_paths = args.files
            is_url = False
        else:  # args.urls
            file_paths = args.urls
            is_url = True
            if not REMOTE_ACCESS_AVAILABLE:
                parser.error("remfile is required for URL access. ")

        # Analyze extensions
        extension_stats = analyze_extensions(file_paths, is_url)

        # Convert to serializable format
        result = [asdict(stat) for stat in extension_stats]

    # Output results
    out = snapshot_result(result, args.output)
    if not args.output:
        print(out)


if __name__ == "__main__":
    main()
