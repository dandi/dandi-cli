"""
BIDS to DuckDB loader with schema-driven dynamic entity parsing.

This module provides functionality to load BIDS datasets into DuckDB tables,
automatically extracting metadata from BIDS-compliant filenames based on the
official BIDS schema specification.

Examples
--------
>>> from pathlib import Path
>>> from dandi.bids_duckdb import BIDSDuckDBLoader
>>>
>>> # Create loader for a BIDS dataset
>>> loader = BIDSDuckDBLoader(Path("/path/to/bids/dataset"))
>>>
>>> # Load various BIDS files
>>> loader.load_participants()
>>> loader.load_sidecar_json()
>>> loader.load_tsv_files()
>>>
>>> # Query the data
>>> df = loader.query('''
...     SELECT p.participant_id, p.age, s.task, s.RepetitionTime
...     FROM participants p
...     JOIN sidecar_metadata s ON 'sub-' || p.participant_id = s.subject
...     WHERE s.task = 'rest'
... ''')
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional
from urllib.request import urlopen

try:
    import duckdb
    from duckdb import DuckDBPyConnection

    HAS_DUCKDB = True
except ImportError:
    HAS_DUCKDB = False
    DuckDBPyConnection = Any  # type: ignore[misc,assignment]

try:
    import yaml

    HAS_YAML = True
except ImportError:
    HAS_YAML = False


class DuckDBNotInstalledError(ImportError):
    """Raised when DuckDB is required but not installed."""

    def __init__(self) -> None:
        super().__init__(
            "DuckDB is required but not installed. "
            "Install it with: pip install duckdb"
        )


class BIDSSchemaError(Exception):
    """Raised when there's an error loading or parsing the BIDS schema."""

    pass


@lru_cache(maxsize=1)
def fetch_bids_schema(
    schema_url: str = "https://raw.githubusercontent.com/bids-standard/bids-specification/master/src/schema/objects/entities.yaml",
) -> dict[str, dict[str, Any]]:
    """
    Fetch and parse the BIDS schema from the official specification.

    Parameters
    ----------
    schema_url : str
        URL to the BIDS schema entities definition. Defaults to the master branch
        on GitHub. Can be changed to point to a specific version tag.

    Returns
    -------
    dict[str, dict[str, Any]]
        Dictionary mapping entity keys to their properties (name, display_name, etc.)

    Raises
    ------
    BIDSSchemaError
        If the schema cannot be fetched or parsed

    Examples
    --------
    >>> schema = fetch_bids_schema()
    >>> schema['subject']['name']
    'sub'
    >>> schema['subject']['display_name']
    'Subject'
    """
    if not HAS_YAML:
        raise BIDSSchemaError(
            "PyYAML is required to parse BIDS schema. Install with: pip install pyyaml"
        )

    try:
        with urlopen(schema_url) as response:
            schema_yaml = response.read().decode("utf-8")
        schema = yaml.safe_load(schema_yaml)
        return schema
    except Exception as e:
        raise BIDSSchemaError(f"Failed to fetch or parse BIDS schema: {e}") from e


def get_entity_patterns(
    schema: Optional[dict[str, dict[str, Any]]] = None,
) -> dict[str, str]:
    """
    Generate regex patterns for extracting BIDS entities from filenames.

    Parameters
    ----------
    schema : dict[str, dict[str, Any]], optional
        BIDS schema dictionary. If None, will fetch the latest schema.

    Returns
    -------
    dict[str, str]
        Dictionary mapping display names (e.g., 'subject') to short entity names
        (e.g., 'sub') for use in regex patterns

    Examples
    --------
    >>> patterns = get_entity_patterns()
    >>> patterns['subject']
    'sub'
    >>> patterns['session']
    'ses'
    """
    if schema is None:
        schema = fetch_bids_schema()

    entity_map = {}
    for entity_key, entity_props in schema.items():
        name = entity_props.get("name")
        display_name = entity_props.get("display_name")
        if name and display_name:
            # Map from display_name to short name for column naming
            # Convert to lowercase and replace spaces with underscores
            col_name = display_name.lower().replace(" ", "_").replace("-", "_")
            entity_map[col_name] = name

    return entity_map


class BIDSDuckDBLoader:
    """
    Load BIDS datasets into DuckDB with schema-driven entity extraction.

    This class automatically parses BIDS filenames and extracts entities
    (subject, session, task, etc.) based on the official BIDS schema,
    making the data queryable via SQL.

    Parameters
    ----------
    bids_root : Path
        Path to the root directory of the BIDS dataset
    db_path : str, optional
        Path to DuckDB database file. If None, uses in-memory database.
    schema_url : str, optional
        URL to BIDS schema. Defaults to latest master branch.
        Can specify a version tag for reproducibility.

    Attributes
    ----------
    bids_root : Path
        Root directory of the BIDS dataset
    conn : DuckDBPyConnection
        DuckDB database connection
    schema : dict
        Loaded BIDS schema
    entities : dict
        Mapping of entity display names to short names

    Examples
    --------
    >>> loader = BIDSDuckDBLoader(Path("/data/bids_dataset"))
    >>> loader.load_participants()
    >>> loader.load_sidecar_json()
    >>> df = loader.query("SELECT * FROM participants LIMIT 5")
    """

    def __init__(
        self,
        bids_root: Path,
        db_path: Optional[str] = None,
        schema_url: Optional[str] = None,
    ):
        if not HAS_DUCKDB:
            raise DuckDBNotInstalledError()

        self.bids_root = Path(bids_root).resolve()
        if not self.bids_root.exists():
            raise FileNotFoundError(f"BIDS root does not exist: {self.bids_root}")

        self.conn = duckdb.connect(db_path or ":memory:")

        # Load BIDS schema
        if schema_url:
            self.schema = fetch_bids_schema(schema_url)
        else:
            self.schema = fetch_bids_schema()

        self.entities = get_entity_patterns(self.schema)

    def _build_entity_extraction_sql(self, alias: str = "filename") -> str:
        """
        Build SQL fragment for extracting all BIDS entities from a filename.

        Parameters
        ----------
        alias : str
            Column alias containing the filename

        Returns
        -------
        str
            SQL fragment with regexp_extract calls for each entity

        Examples
        --------
        >>> loader = BIDSDuckDBLoader(Path("/data/bids"))
        >>> sql = loader._build_entity_extraction_sql("filename")
        >>> "regexp_extract(filename, 'sub-([^_/]+)', 1) as subject" in sql
        True
        """
        extracts = []
        for col_name, short_name in sorted(self.entities.items()):
            # Build regex pattern: entity_name-value
            # Capture until next underscore, slash, or dot
            pattern = f"{short_name}-([^_/\\.]+)"
            extract_sql = f"regexp_extract({alias}, '{pattern}', 1) as {col_name}"
            extracts.append(extract_sql)

        return ",\n            ".join(extracts)

    def load_dataset_description(self) -> None:
        """
        Load dataset_description.json into a table.

        Creates a table named 'dataset_description' with the contents
        of the BIDS dataset_description.json file.

        Raises
        ------
        FileNotFoundError
            If dataset_description.json does not exist
        """
        desc_path = self.bids_root / "dataset_description.json"
        if not desc_path.exists():
            raise FileNotFoundError(
                f"dataset_description.json not found in {self.bids_root}"
            )

        self.conn.execute(
            f"""
            CREATE OR REPLACE TABLE dataset_description AS
            SELECT * FROM read_json('{desc_path}')
        """
        )

    def load_participants(self) -> None:
        """
        Load participants.tsv into a table.

        Creates a table named 'participants' with the contents of the
        BIDS participants.tsv file if it exists.

        Notes
        -----
        If participants.tsv doesn't exist, this method does nothing.
        """
        participants_path = self.bids_root / "participants.tsv"
        if participants_path.exists():
            self.conn.execute(
                f"""
                CREATE OR REPLACE TABLE participants AS
                SELECT * FROM read_csv(
                    '{participants_path}',
                    delim='\\t',
                    header=true,
                    auto_detect=true
                )
            """
            )

    def load_sidecar_json(
        self,
        datatype: Optional[str] = None,
        suffix: Optional[str] = None,
        table_name: str = "sidecar_metadata",
    ) -> None:
        """
        Load all sidecar JSON files with parsed BIDS entities.

        Creates a table with JSON metadata and extracted BIDS entities
        (subject, session, task, etc.) from filenames.

        Parameters
        ----------
        datatype : str, optional
            Filter to specific BIDS datatype (e.g., 'func', 'anat').
            If None, loads all datatypes.
        suffix : str, optional
            Filter to specific suffix pattern (e.g., 'bold', 'T1w').
            If None, loads all JSON files.
        table_name : str
            Name for the created table. Default is 'sidecar_metadata'.

        Examples
        --------
        >>> loader.load_sidecar_json(datatype='func', suffix='bold')
        >>> df = loader.query("SELECT * FROM sidecar_metadata WHERE task='rest'")
        """
        # Build file pattern
        if datatype:
            pattern = f"{self.bids_root}/**/{datatype}/*"
        else:
            pattern = f"{self.bids_root}/**/*"

        if suffix:
            pattern += f"{suffix}.json"
        else:
            pattern += ".json"

        entity_extracts = self._build_entity_extraction_sql("filename")

        self.conn.execute(
            f"""
            CREATE OR REPLACE TABLE {table_name} AS
            SELECT
                filename,
                {entity_extracts},
                json_data.*
            FROM read_json(
                '{pattern}',
                filename=true,
                union_by_name=true,
                ignore_errors=true
            ) as json_data
            WHERE filename NOT LIKE '%dataset_description.json'
              AND filename NOT LIKE '%participants.json'
        """
        )

    def load_tsv_files(
        self,
        file_type: str = "*",
        table_name: str = "tsv_data",
    ) -> None:
        """
        Load all TSV files (events, channels, etc.) with parsed entities.

        Parameters
        ----------
        file_type : str
            Pattern to match TSV file types (e.g., 'events', 'channels').
            Use '*' to load all TSV files.
        table_name : str
            Name for the created table. Default is 'tsv_data'.

        Examples
        --------
        >>> loader.load_tsv_files(file_type='events')
        >>> df = loader.query("SELECT * FROM tsv_data WHERE trial_type='go'")
        """
        pattern = f"{self.bids_root}/**/*{file_type}.tsv"
        entity_extracts = self._build_entity_extraction_sql("filename")

        self.conn.execute(
            f"""
            CREATE OR REPLACE TABLE {table_name} AS
            SELECT
                filename,
                {entity_extracts},
                regexp_extract(filename, '([a-z]+)\\.tsv$', 1) as file_type,
                tsv.*
            FROM read_csv(
                '{pattern}',
                delim='\\t',
                filename=true,
                union_by_name=true,
                ignore_errors=true,
                auto_detect=true
            ) as tsv
            WHERE filename NOT LIKE '%participants.tsv'
        """
        )

    def load_bids_metadata(
        self,
        datatype: Optional[str] = None,
    ) -> None:
        """
        Load all JSON and TSV files for a complete metadata view.

        This is a convenience method that loads both sidecar JSON files
        and TSV files in one call.

        Parameters
        ----------
        datatype : str, optional
            Filter to specific BIDS datatype. If None, loads all.

        Examples
        --------
        >>> loader.load_bids_metadata(datatype='func')
        >>> # Now both sidecar_metadata and tsv_data tables are populated
        """
        self.load_sidecar_json(datatype=datatype)
        self.load_tsv_files()

    def query(self, sql: str) -> Any:
        """
        Execute SQL query and return results as pandas DataFrame.

        Parameters
        ----------
        sql : str
            SQL query to execute

        Returns
        -------
        pandas.DataFrame
            Query results

        Examples
        --------
        >>> df = loader.query('''
        ...     SELECT subject, session, COUNT(*) as n_runs
        ...     FROM sidecar_metadata
        ...     WHERE task = 'rest'
        ...     GROUP BY subject, session
        ... ''')
        """
        return self.conn.execute(sql).fetchdf()

    def get_tables(self) -> list[str]:
        """
        Get list of all tables in the database.

        Returns
        -------
        list[str]
            List of table names

        Examples
        --------
        >>> loader.get_tables()
        ['participants', 'sidecar_metadata', 'tsv_data']
        """
        result = self.conn.execute("SHOW TABLES").fetchall()
        return [row[0] for row in result]

    def get_schema_info(self) -> dict[str, Any]:
        """
        Get information about the loaded BIDS schema.

        Returns
        -------
        dict
            Information about schema version and available entities

        Examples
        --------
        >>> info = loader.get_schema_info()
        >>> info['entities']
        {'subject': 'sub', 'session': 'ses', 'task': 'task', ...}
        """
        return {
            "entities": self.entities,
            "num_entities": len(self.entities),
            "entity_names": sorted(self.entities.keys()),
        }

    def close(self) -> None:
        """Close the DuckDB connection."""
        if hasattr(self, "conn"):
            self.conn.close()

    def __enter__(self) -> BIDSDuckDBLoader:
        """Context manager entry."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit."""
        self.close()

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"BIDSDuckDBLoader(bids_root={self.bids_root}, "
            f"tables={self.get_tables()})"
        )
