#!/usr/bin/env python
"""
Example usage of the BIDS DuckDB loader.

This script demonstrates how to load BIDS datasets into DuckDB
for efficient querying and analysis.

Requirements:
    pip install duckdb pyyaml

Usage:
    python examples/bids_duckdb_example.py /path/to/bids/dataset
"""

from __future__ import annotations

import sys
from pathlib import Path

from dandi.bids_duckdb import BIDSDuckDBLoader


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python bids_duckdb_example.py /path/to/bids/dataset")
        sys.exit(1)

    bids_root = Path(sys.argv[1])

    if not bids_root.exists():
        print(f"Error: BIDS dataset not found at {bids_root}")
        sys.exit(1)

    # Create loader
    print(f"Loading BIDS dataset from: {bids_root}")
    with BIDSDuckDBLoader(bids_root) as loader:
        # Display schema information
        print("\n=== BIDS Schema Information ===")
        schema_info = loader.get_schema_info()
        print(f"Number of entities: {schema_info['num_entities']}")
        print(f"Available entities: {', '.join(sorted(schema_info['entity_names'][:10]))}...")

        # Load dataset components
        print("\n=== Loading Dataset ===")
        try:
            loader.load_dataset_description()
            print("✓ Loaded dataset_description.json")
        except Exception as e:
            print(f"✗ Could not load dataset_description.json: {e}")

        try:
            loader.load_participants()
            print("✓ Loaded participants.tsv")
        except Exception as e:
            print(f"✗ Could not load participants.tsv: {e}")

        try:
            loader.load_sidecar_json()
            print("✓ Loaded sidecar JSON files")
        except Exception as e:
            print(f"✗ Could not load sidecar JSON files: {e}")

        try:
            loader.load_tsv_files()
            print("✓ Loaded TSV files")
        except Exception as e:
            print(f"✗ Could not load TSV files: {e}")

        # Show available tables
        print("\n=== Available Tables ===")
        tables = loader.get_tables()
        for table in tables:
            print(f"  - {table}")

        # Example queries
        print("\n=== Example Queries ===")

        # Query 1: Participants summary
        if "participants" in tables:
            print("\n1. Participants Summary:")
            try:
                df = loader.query(
                    """
                    SELECT COUNT(*) as n_participants
                    FROM participants
                """
                )
                print(f"   Total participants: {df['n_participants'][0]}")
            except Exception as e:
                print(f"   Error: {e}")

        # Query 2: Functional scans summary
        if "sidecar_metadata" in tables:
            print("\n2. Functional Scans by Task:")
            try:
                df = loader.query(
                    """
                    SELECT
                        task,
                        COUNT(*) as n_scans,
                        AVG(RepetitionTime) as avg_tr
                    FROM sidecar_metadata
                    WHERE task IS NOT NULL
                    GROUP BY task
                    ORDER BY n_scans DESC
                """
                )
                print(df.to_string(index=False))
            except Exception as e:
                print(f"   Error: {e}")

        # Query 3: Join participants with scans
        if "participants" in tables and "sidecar_metadata" in tables:
            print("\n3. Scans per Participant:")
            try:
                df = loader.query(
                    """
                    SELECT
                        p.participant_id,
                        p.age,
                        COUNT(DISTINCT s.session) as n_sessions,
                        COUNT(*) as n_scans
                    FROM participants p
                    LEFT JOIN sidecar_metadata s
                        ON p.participant_id = 'sub-' || s.subject
                    GROUP BY p.participant_id, p.age
                    ORDER BY p.participant_id
                    LIMIT 10
                """
                )
                print(df.to_string(index=False))
            except Exception as e:
                print(f"   Error: {e}")

        # Query 4: Events analysis
        if "tsv_data" in tables:
            print("\n4. Event Types Distribution:")
            try:
                df = loader.query(
                    """
                    SELECT
                        trial_type,
                        COUNT(*) as n_events,
                        AVG(duration) as avg_duration
                    FROM tsv_data
                    WHERE trial_type IS NOT NULL
                    GROUP BY trial_type
                    ORDER BY n_events DESC
                """
                )
                print(df.to_string(index=False))
            except Exception as e:
                print(f"   Error: {e}")

        # Advanced: Export to persistent database
        print("\n=== Export to File ===")
        db_path = bids_root / "bids_metadata.duckdb"
        print(f"To create a persistent database, use:")
        print(f"  loader = BIDSDuckDBLoader(bids_root, db_path='{db_path}')")
        print(f"Then you can query it later without reloading the data.")

        # Custom analysis example
        print("\n=== Custom Analysis Example ===")
        print(
            """
You can perform complex analyses by combining tables:

# Example: Find all subjects with at least 2 sessions
df = loader.query('''
    SELECT
        subject,
        COUNT(DISTINCT session) as n_sessions,
        COUNT(DISTINCT task) as n_tasks
    FROM sidecar_metadata
    WHERE subject IS NOT NULL
    GROUP BY subject
    HAVING COUNT(DISTINCT session) >= 2
''')

# Example: Get all task-rest scans with their parameters
df = loader.query('''
    SELECT
        subject,
        session,
        run,
        RepetitionTime,
        EchoTime,
        FlipAngle
    FROM sidecar_metadata
    WHERE task = 'rest'
    ORDER BY subject, session, run
''')
"""
        )

        print("\n=== Done ===")
        print(f"Loaded {len(tables)} tables from BIDS dataset")


if __name__ == "__main__":
    main()
