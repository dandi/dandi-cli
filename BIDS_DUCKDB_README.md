# BIDS DuckDB Assistant Implementation

This document describes the implementation of a schema-driven BIDS to DuckDB loader that dynamically extracts metadata from BIDS-compliant file hierarchies.

## Overview

The `bids_duckdb` module provides a solution to the challenge of loading BIDS datasets into DuckDB. While DuckDB's `hive_partitioning` expects `key=value/` directory structures, BIDS encodes metadata in filenames using entity-value pairs (e.g., `sub-01_ses-02_task-rest_bold.json`).

## Key Innovation

This implementation:

1. **Fetches the BIDS schema** from the official specification (https://github.com/bids-standard/bids-specification)
2. **Parses entity definitions** to extract mappings between short names (`sub`, `ses`, `task`) and display names (`subject`, `session`, `task`)
3. **Dynamically generates SQL** with regex patterns for all BIDS entities
4. **Works across BIDS versions** by allowing specification of schema URL/version

## Files Created

### Core Module
- **`dandi/bids_duckdb.py`**: Main implementation
  - `BIDSDuckDBLoader` class for loading BIDS datasets
  - `fetch_bids_schema()` function to retrieve and cache BIDS schema
  - `get_entity_patterns()` to extract entity mappings
  - Dynamic SQL generation based on schema

### Tests
- **`dandi/tests/test_bids_duckdb.py`**: Comprehensive test suite
  - Tests for schema fetching and parsing
  - Tests for entity extraction from filenames
  - Tests for loading participants, JSON sidecars, and TSV files
  - Tests for complex SQL joins and queries
  - All tests marked with `@pytest.mark.ai_generated` as per project guidelines

### Documentation
- **`docs/bids_duckdb.md`**: Complete user documentation
  - API reference
  - Usage examples
  - Performance tips
  - Comparison with hive_partitioning

### Examples
- **`examples/bids_duckdb_example.py`**: Executable example script
  - Demonstrates loading a BIDS dataset
  - Shows common query patterns
  - Provides analysis examples

### Configuration
- **`pyproject.toml`**: Updated with optional dependencies
  - Added `duckdb` extras group with `duckdb >= 0.9.0` and `pyyaml >= 5.0`
  - Included in `all` extras

- **`tox.ini`**: Updated pytest configuration
  - Added `ai_generated` marker for test tracking

## How It Works

### 1. Schema-Driven Approach

Instead of hard-coding BIDS entities, the loader fetches the official schema:

```python
schema = fetch_bids_schema()
# Returns dict with all entity definitions from:
# https://raw.githubusercontent.com/bids-standard/bids-specification/master/src/schema/objects/entities.yaml
```

The schema contains ~31 entities with structure:
```yaml
subject:
  name: sub
  display_name: Subject
  description: |
    A person or animal participating in the study.
  type: string
  format: label
```

### 2. Dynamic Entity Extraction

The loader generates regex patterns for each entity:

```python
entity_patterns = get_entity_patterns(schema)
# {'subject': 'sub', 'session': 'ses', 'task': 'task', ...}
```

### 3. SQL Generation

For each file type (JSON, TSV), the loader builds SQL that extracts all entities:

```sql
CREATE TABLE sidecar_metadata AS
SELECT
    filename,
    regexp_extract(filename, 'sub-([^_/\.]+)', 1) as subject,
    regexp_extract(filename, 'ses-([^_/\.]+)', 1) as session,
    regexp_extract(filename, 'task-([^_/\.]+)', 1) as task,
    -- ... all other BIDS entities dynamically added ...
    json_data.*
FROM read_json('path/**/*.json', filename=true, union_by_name=true)
```

## Usage Examples

### Basic Loading

```python
from pathlib import Path
from dandi.bids_duckdb import BIDSDuckDBLoader

with BIDSDuckDBLoader(Path("/data/bids")) as loader:
    loader.load_participants()
    loader.load_sidecar_json()
    loader.load_tsv_files()

    # Query across the dataset
    df = loader.query("""
        SELECT subject, COUNT(*) as n_scans
        FROM sidecar_metadata
        GROUP BY subject
    """)
```

### Version-Specific Schema

```python
# Use a specific BIDS version
schema_url = "https://raw.githubusercontent.com/bids-standard/bids-specification/v1.9.0/src/schema/objects/entities.yaml"
loader = BIDSDuckDBLoader(bids_root, schema_url=schema_url)
```

### Complex Analysis

```python
# Join participants with scan metadata
df = loader.query("""
    SELECT
        p.participant_id,
        p.age,
        p.sex,
        s.task,
        COUNT(*) as n_scans,
        AVG(s.RepetitionTime) as mean_tr
    FROM participants p
    JOIN sidecar_metadata s ON p.participant_id = 'sub-' || s.subject
    GROUP BY p.participant_id, p.age, p.sex, s.task
""")
```

## Advantages

### Over hive_partitioning
- **Flexible file naming**: Handles BIDS entity-value pairs in filenames
- **Missing entities**: Gracefully handles files with subset of entities (NULL values)
- **Schema validation**: Ensures extracted entities match BIDS specification

### Over manual parsing
- **Version-agnostic**: Works with different BIDS versions automatically
- **Complete coverage**: Extracts all 31+ BIDS entities without hard-coding
- **Maintainable**: Updates automatically when BIDS schema evolves

## Dependencies

The module requires:
- `duckdb >= 0.9.0`: For the analytical database engine
- `pyyaml >= 5.0`: For parsing BIDS schema YAML files

These are optional dependencies that can be installed with:
```bash
pip install dandi[duckdb]
```

## Relevant DuckDB Features Used

1. **`filename=true`**: Captures filepath for entity extraction
2. **`union_by_name=true`**: Handles varying JSON/TSV schemas
3. **`ignore_errors=true`**: Gracefully handles malformed files
4. **`regexp_extract()`**: Extracts entities using regex patterns
5. **Auto-detection**: Automatically infers column types from data

## Testing

Run tests with:
```bash
# Install dependencies
pip install duckdb pyyaml

# Run tests
tox -e py3 -- dandi/tests/test_bids_duckdb.py -v
```

All tests are marked with `@pytest.mark.ai_generated` as per project conventions.

## Future Enhancements

Potential improvements:
1. **Caching**: Cache parsed schemas locally to reduce network calls
2. **Validation**: Integrate with BIDS validator for data quality checks
3. **Views**: Create predefined SQL views for common analysis patterns
4. **Export**: Support exporting to Parquet for long-term storage
5. **Streaming**: Handle very large datasets with streaming/partitioned loading

## References

- **BIDS Specification**: https://bids-specification.readthedocs.io/
- **BIDS Schema**: https://github.com/bids-standard/bids-specification/tree/master/src/schema
- **DuckDB Documentation**: https://duckdb.org/docs/
- **Related Discussion**: https://github.com/duckdb/duckdb/discussions/6897

## Author Notes

This implementation was created to address the challenge of loading BIDS datasets into DuckDB when the file hierarchy doesn't conform to hive partitioning conventions. By reading the BIDS schema directly and dynamically generating SQL, the solution is both flexible and maintainable across different BIDS versions.
