# BIDS DuckDB Loader

The `dandi.bids_duckdb` module provides a schema-driven approach to loading BIDS datasets into DuckDB for efficient querying and analysis.

## Overview

BIDS (Brain Imaging Data Structure) datasets use a hierarchical structure with metadata encoded in filenames using entity-value pairs (e.g., `sub-01_ses-02_task-rest_bold.json`). This module automatically:

1. Fetches the official BIDS schema to understand all available entities
2. Parses BIDS filenames to extract entity values
3. Loads JSON sidecars and TSV files into queryable DuckDB tables
4. Enables SQL-based analysis across the entire dataset

## Key Features

- **Schema-driven**: Automatically adapts to different BIDS versions by reading the official schema
- **Dynamic entity extraction**: Extracts all BIDS entities (subject, session, task, run, etc.) from filenames
- **Flexible querying**: Use standard SQL to analyze BIDS metadata
- **Multiple file types**: Supports JSON sidecars, TSV files, and participants data
- **Efficient**: Leverages DuckDB's performance for fast analytical queries

## Installation

The BIDS DuckDB loader requires additional dependencies:

```bash
pip install duckdb pyyaml
```

Or install with the extras:

```bash
pip install dandi[duckdb]
```

## Quick Start

```python
from pathlib import Path
from dandi.bids_duckdb import BIDSDuckDBLoader

# Create loader
bids_root = Path("/path/to/bids/dataset")
with BIDSDuckDBLoader(bids_root) as loader:
    # Load data
    loader.load_participants()
    loader.load_sidecar_json()
    loader.load_tsv_files()

    # Query with SQL
    df = loader.query("""
        SELECT
            p.participant_id,
            p.age,
            COUNT(*) as n_scans
        FROM participants p
        JOIN sidecar_metadata s
            ON p.participant_id = 'sub-' || s.subject
        GROUP BY p.participant_id, p.age
    """)

    print(df)
```

## How It Works

### 1. Schema Loading

The loader fetches the BIDS schema from the official specification:

```python
from dandi.bids_duckdb import fetch_bids_schema, get_entity_patterns

# Fetch the schema
schema = fetch_bids_schema()

# Get entity mappings (display_name -> short_name)
patterns = get_entity_patterns()
# {'subject': 'sub', 'session': 'ses', 'task': 'task', ...}
```

### 2. Entity Extraction

For each file, the loader extracts BIDS entities using regex patterns generated from the schema:

```
Filename: sub-01_ses-02_task-rest_run-01_bold.json

Extracted entities:
- subject: 01
- session: 02
- task: rest
- run: 01
```

### 3. SQL Generation

The loader dynamically generates SQL that includes all BIDS entities as columns:

```sql
SELECT
    filename,
    regexp_extract(filename, 'sub-([^_/\.]+)', 1) as subject,
    regexp_extract(filename, 'ses-([^_/\.]+)', 1) as session,
    regexp_extract(filename, 'task-([^_/\.]+)', 1) as task,
    regexp_extract(filename, 'run-([^_/\.]+)', 1) as run,
    -- ... all other BIDS entities ...
    json_data.*
FROM read_json('path/to/bids/**/*.json', filename=true, union_by_name=true)
```

## API Reference

### BIDSDuckDBLoader

Main class for loading BIDS datasets into DuckDB.

```python
loader = BIDSDuckDBLoader(
    bids_root: Path,           # Path to BIDS dataset root
    db_path: Optional[str],    # Path to DuckDB file (None for in-memory)
    schema_url: Optional[str]  # URL to BIDS schema (None for latest)
)
```

**Methods:**

- `load_dataset_description()` - Load `dataset_description.json`
- `load_participants()` - Load `participants.tsv`
- `load_sidecar_json(datatype=None, suffix=None, table_name='sidecar_metadata')` - Load JSON sidecars
- `load_tsv_files(file_type='*', table_name='tsv_data')` - Load TSV files (events, channels, etc.)
- `load_bids_metadata(datatype=None)` - Load both JSON and TSV files
- `query(sql: str)` - Execute SQL and return pandas DataFrame
- `get_tables()` - List all tables in the database
- `get_schema_info()` - Get information about loaded BIDS schema

### Functions

```python
# Fetch BIDS schema from specification
schema = fetch_bids_schema(schema_url: str = "...")

# Get entity patterns from schema
patterns = get_entity_patterns(schema: Optional[dict] = None)
```

## Examples

### Example 1: Participant Demographics

```python
loader.load_participants()

df = loader.query("""
    SELECT
        sex,
        COUNT(*) as n_participants,
        AVG(age) as mean_age,
        MIN(age) as min_age,
        MAX(age) as max_age
    FROM participants
    GROUP BY sex
""")
```

### Example 2: Scan Parameters by Task

```python
loader.load_sidecar_json(datatype='func')

df = loader.query("""
    SELECT
        task,
        COUNT(*) as n_scans,
        AVG(RepetitionTime) as mean_tr,
        AVG(EchoTime) as mean_te
    FROM sidecar_metadata
    WHERE task IS NOT NULL
    GROUP BY task
    ORDER BY n_scans DESC
""")
```

### Example 3: Events Analysis

```python
loader.load_tsv_files(file_type='events')

df = loader.query("""
    SELECT
        subject,
        task,
        trial_type,
        COUNT(*) as n_trials,
        AVG(duration) as mean_duration
    FROM tsv_data
    WHERE trial_type IS NOT NULL
    GROUP BY subject, task, trial_type
""")
```

### Example 4: Multi-Session Analysis

```python
loader.load_sidecar_json()

df = loader.query("""
    SELECT
        subject,
        COUNT(DISTINCT session) as n_sessions,
        COUNT(DISTINCT task) as n_tasks,
        COUNT(*) as total_scans
    FROM sidecar_metadata
    WHERE subject IS NOT NULL
    GROUP BY subject
    HAVING COUNT(DISTINCT session) > 1
    ORDER BY n_sessions DESC
""")
```

### Example 5: Persistent Database

```python
# Create persistent database file
db_path = "/path/to/bids_metadata.duckdb"
loader = BIDSDuckDBLoader(bids_root, db_path=db_path)

loader.load_participants()
loader.load_sidecar_json()
loader.load_tsv_files()
loader.close()

# Later, reopen and query without reloading
conn = duckdb.connect(db_path)
df = conn.execute("SELECT * FROM participants").fetchdf()
```

## BIDS Schema Versions

By default, the loader fetches the schema from the master branch of the BIDS specification repository. To use a specific version:

```python
# Use a specific version tag
schema_url = "https://raw.githubusercontent.com/bids-standard/bids-specification/v1.9.0/src/schema/objects/entities.yaml"
loader = BIDSDuckDBLoader(bids_root, schema_url=schema_url)
```

Or use a local schema file:

```python
# Load from local file
import yaml
with open('local_schema.yaml') as f:
    schema = yaml.safe_load(f)

from dandi.bids_duckdb import get_entity_patterns
patterns = get_entity_patterns(schema)
```

## Advantages Over hive_partitioning

While DuckDB's `hive_partitioning` expects directory structures like `key=value/`, BIDS uses entity-value pairs within filenames. This module solves that by:

1. **Parsing filenames**: Extracts entities using regex patterns
2. **Schema-driven**: Automatically includes all BIDS-defined entities
3. **Version-agnostic**: Works with different BIDS versions by fetching the appropriate schema
4. **Flexible**: Handles missing entities gracefully (NULL values)

## Performance Tips

1. **Filter early**: Use `datatype` and `suffix` parameters to limit loaded files
2. **Persistent database**: Use `db_path` to avoid reloading on each analysis
3. **Indexed queries**: Create indexes on frequently queried columns
4. **Batch operations**: Load all data once, then run multiple queries

```python
# Create indexes for faster queries
loader.conn.execute("CREATE INDEX idx_subject ON sidecar_metadata(subject)")
loader.conn.execute("CREATE INDEX idx_task ON sidecar_metadata(task)")
```

## Limitations

1. **Schema format**: Currently supports YAML schema format from GitHub
2. **Entity ambiguity**: Some custom entities might not be in the official schema
3. **Nested JSON**: Deep JSON nesting may require additional unnesting in queries
4. **File size**: Very large datasets might benefit from partitioned loading

## Related Tools

- [bidsschematools](https://github.com/bids-standard/bids-specification): Official BIDS schema tools
- [pybids](https://github.com/bids-standard/pybids): Python library for BIDS datasets
- [DuckDB](https://duckdb.org/): High-performance analytical database

## Contributing

To add support for new BIDS file types or improve entity extraction, see the implementation in `dandi/bids_duckdb.py`.

## See Also

- [BIDS Specification](https://bids-specification.readthedocs.io/)
- [DuckDB Documentation](https://duckdb.org/docs/)
- [BIDS Schema on GitHub](https://github.com/bids-standard/bids-specification/tree/master/src/schema)
