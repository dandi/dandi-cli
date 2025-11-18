"""Tests for BIDS to DuckDB loader."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from dandi.bids_duckdb import (
    BIDSDuckDBLoader,
    DuckDBNotInstalledError,
    fetch_bids_schema,
    get_entity_patterns,
)

duckdb = pytest.importorskip("duckdb")
yaml = pytest.importorskip("yaml")


@pytest.fixture
def mock_bids_dataset(tmp_path: Path) -> Path:
    """
    Create a minimal BIDS dataset for testing.

    Structure:
        dataset/
        ├── dataset_description.json
        ├── participants.tsv
        ├── sub-01/
        │   ├── ses-01/
        │   │   ├── func/
        │   │   │   ├── sub-01_ses-01_task-rest_bold.json
        │   │   │   └── sub-01_ses-01_task-rest_events.tsv
        │   │   └── anat/
        │   │       └── sub-01_ses-01_T1w.json
        │   └── ses-02/
        │       └── func/
        │           └── sub-01_ses-02_task-nback_run-01_bold.json
        └── sub-02/
            └── anat/
                └── sub-02_T1w.json
    """
    dataset_root = tmp_path / "bids_dataset"
    dataset_root.mkdir()

    # Create dataset_description.json
    dataset_desc = {
        "Name": "Test Dataset",
        "BIDSVersion": "1.9.0",
        "DatasetType": "raw",
    }
    (dataset_root / "dataset_description.json").write_text(json.dumps(dataset_desc))

    # Create participants.tsv
    participants_tsv = "participant_id\tage\tsex\n" "sub-01\t25\tF\n" "sub-02\t30\tM\n"
    (dataset_root / "participants.tsv").write_text(participants_tsv)

    # Create sub-01/ses-01/func
    func_dir = dataset_root / "sub-01" / "ses-01" / "func"
    func_dir.mkdir(parents=True)

    bold_json = {
        "RepetitionTime": 2.0,
        "EchoTime": 0.03,
        "FlipAngle": 90,
        "TaskName": "rest",
    }
    (func_dir / "sub-01_ses-01_task-rest_bold.json").write_text(json.dumps(bold_json))

    events_tsv = "onset\tduration\ttrial_type\n" "0.0\t1.5\tgo\n" "2.0\t1.5\tstop\n"
    (func_dir / "sub-01_ses-01_task-rest_events.tsv").write_text(events_tsv)

    # Create sub-01/ses-01/anat
    anat_dir = dataset_root / "sub-01" / "ses-01" / "anat"
    anat_dir.mkdir(parents=True)

    t1w_json = {"FlipAngle": 8, "EchoTime": 0.00456}
    (anat_dir / "sub-01_ses-01_T1w.json").write_text(json.dumps(t1w_json))

    # Create sub-01/ses-02/func
    func_dir2 = dataset_root / "sub-01" / "ses-02" / "func"
    func_dir2.mkdir(parents=True)

    nback_json = {
        "RepetitionTime": 2.5,
        "EchoTime": 0.035,
        "TaskName": "nback",
    }
    (func_dir2 / "sub-01_ses-02_task-nback_run-01_bold.json").write_text(
        json.dumps(nback_json)
    )

    # Create sub-02/anat
    anat_dir2 = dataset_root / "sub-02" / "anat"
    anat_dir2.mkdir(parents=True)

    t1w_json2 = {"FlipAngle": 8, "EchoTime": 0.00456}
    (anat_dir2 / "sub-02_T1w.json").write_text(json.dumps(t1w_json2))

    return dataset_root


@pytest.mark.ai_generated
def test_fetch_bids_schema() -> None:
    """Test fetching and parsing the BIDS schema."""
    schema = fetch_bids_schema()

    # Check that schema was loaded
    assert isinstance(schema, dict)
    assert len(schema) > 0

    # Check for known entities
    assert "subject" in schema
    assert schema["subject"]["name"] == "sub"
    assert "session" in schema
    assert schema["session"]["name"] == "ses"
    assert "task" in schema
    assert schema["task"]["name"] == "task"


@pytest.mark.ai_generated
def test_get_entity_patterns() -> None:
    """Test entity pattern extraction from schema."""
    patterns = get_entity_patterns()

    # Check that patterns were generated
    assert isinstance(patterns, dict)
    assert len(patterns) > 0

    # Check for known entities with proper mapping
    assert "subject" in patterns
    assert patterns["subject"] == "sub"
    assert "session" in patterns
    assert patterns["session"] == "ses"
    assert "task" in patterns
    assert patterns["task"] == "task"
    assert "run" in patterns
    assert patterns["run"] == "run"


@pytest.mark.ai_generated
def test_bids_duckdb_loader_init(mock_bids_dataset: Path) -> None:
    """Test BIDSDuckDBLoader initialization."""
    loader = BIDSDuckDBLoader(mock_bids_dataset)

    assert loader.bids_root == mock_bids_dataset.resolve()
    assert loader.conn is not None
    assert isinstance(loader.schema, dict)
    assert isinstance(loader.entities, dict)
    assert len(loader.entities) > 0

    loader.close()


@pytest.mark.ai_generated
def test_bids_duckdb_loader_nonexistent_path() -> None:
    """Test that loader raises error for nonexistent path."""
    with pytest.raises(FileNotFoundError):
        BIDSDuckDBLoader(Path("/nonexistent/path"))


@pytest.mark.ai_generated
def test_load_dataset_description(mock_bids_dataset: Path) -> None:
    """Test loading dataset_description.json."""
    with BIDSDuckDBLoader(mock_bids_dataset) as loader:
        loader.load_dataset_description()

        df = loader.query("SELECT * FROM dataset_description")
        assert len(df) == 1
        assert df["Name"][0] == "Test Dataset"
        assert df["BIDSVersion"][0] == "1.9.0"


@pytest.mark.ai_generated
def test_load_participants(mock_bids_dataset: Path) -> None:
    """Test loading participants.tsv."""
    with BIDSDuckDBLoader(mock_bids_dataset) as loader:
        loader.load_participants()

        df = loader.query("SELECT * FROM participants ORDER BY participant_id")
        assert len(df) == 2
        assert df["participant_id"].tolist() == ["sub-01", "sub-02"]
        assert df["age"].tolist() == [25, 30]
        assert df["sex"].tolist() == ["F", "M"]


@pytest.mark.ai_generated
def test_load_sidecar_json(mock_bids_dataset: Path) -> None:
    """Test loading sidecar JSON files with entity extraction."""
    with BIDSDuckDBLoader(mock_bids_dataset) as loader:
        loader.load_sidecar_json()

        # Check that table was created
        assert "sidecar_metadata" in loader.get_tables()

        # Query all sidecar files
        df = loader.query("SELECT * FROM sidecar_metadata")
        assert len(df) > 0

        # Check entity extraction for a specific file
        rest_bold = loader.query(
            """
            SELECT subject, session, task, RepetitionTime
            FROM sidecar_metadata
            WHERE task = 'rest'
        """
        )
        assert len(rest_bold) == 1
        assert rest_bold["subject"][0] == "01"
        assert rest_bold["session"][0] == "01"
        assert rest_bold["task"][0] == "rest"
        assert rest_bold["RepetitionTime"][0] == 2.0


@pytest.mark.ai_generated
def test_load_sidecar_json_filtered(mock_bids_dataset: Path) -> None:
    """Test loading sidecar JSON with datatype filter."""
    with BIDSDuckDBLoader(mock_bids_dataset) as loader:
        loader.load_sidecar_json(datatype="func", suffix="bold")

        df = loader.query("SELECT * FROM sidecar_metadata")
        # Should have 2 func/bold files (sub-01/ses-01 and sub-01/ses-02)
        assert len(df) == 2

        # All should have RepetitionTime
        assert "RepetitionTime" in df.columns


@pytest.mark.ai_generated
def test_load_tsv_files(mock_bids_dataset: Path) -> None:
    """Test loading TSV files with entity extraction."""
    with BIDSDuckDBLoader(mock_bids_dataset) as loader:
        loader.load_tsv_files(file_type="events")

        # Check that table was created
        assert "tsv_data" in loader.get_tables()

        # Query TSV data
        df = loader.query("SELECT * FROM tsv_data")
        assert len(df) == 2  # Two rows in events.tsv

        # Check entity extraction
        assert "subject" in df.columns
        assert "session" in df.columns
        assert "task" in df.columns

        # Check content
        assert "trial_type" in df.columns
        assert set(df["trial_type"]) == {"go", "stop"}


@pytest.mark.ai_generated
def test_complex_query_join(mock_bids_dataset: Path) -> None:
    """Test complex query joining participants and metadata."""
    with BIDSDuckDBLoader(mock_bids_dataset) as loader:
        loader.load_participants()
        loader.load_sidecar_json()

        # Join participants with sidecar metadata
        df = loader.query(
            """
            SELECT
                p.participant_id,
                p.age,
                s.task,
                s.RepetitionTime
            FROM participants p
            JOIN sidecar_metadata s
                ON p.participant_id = 'sub-' || s.subject
            WHERE s.task IS NOT NULL
            ORDER BY p.participant_id, s.task
        """
        )

        assert len(df) > 0
        assert "participant_id" in df.columns
        assert "age" in df.columns
        assert "task" in df.columns


@pytest.mark.ai_generated
def test_get_tables(mock_bids_dataset: Path) -> None:
    """Test getting list of tables."""
    with BIDSDuckDBLoader(mock_bids_dataset) as loader:
        # Initially no tables
        assert len(loader.get_tables()) == 0

        # Load some data
        loader.load_participants()
        loader.load_sidecar_json()

        tables = loader.get_tables()
        assert "participants" in tables
        assert "sidecar_metadata" in tables


@pytest.mark.ai_generated
def test_get_schema_info(mock_bids_dataset: Path) -> None:
    """Test getting schema information."""
    with BIDSDuckDBLoader(mock_bids_dataset) as loader:
        info = loader.get_schema_info()

        assert "entities" in info
        assert "num_entities" in info
        assert "entity_names" in info

        assert isinstance(info["entities"], dict)
        assert info["num_entities"] > 0
        assert "subject" in info["entity_names"]
        assert "session" in info["entity_names"]
        assert "task" in info["entity_names"]


@pytest.mark.ai_generated
def test_context_manager(mock_bids_dataset: Path) -> None:
    """Test using loader as context manager."""
    with BIDSDuckDBLoader(mock_bids_dataset) as loader:
        loader.load_participants()
        assert "participants" in loader.get_tables()
    # Connection should be closed after exiting context


@pytest.mark.ai_generated
def test_entity_extraction_multiple_entities(mock_bids_dataset: Path) -> None:
    """Test that multiple entities are extracted correctly."""
    with BIDSDuckDBLoader(mock_bids_dataset) as loader:
        loader.load_sidecar_json()

        # Check file with multiple entities
        df = loader.query(
            """
            SELECT subject, session, task, run
            FROM sidecar_metadata
            WHERE task = 'nback'
        """
        )

        assert len(df) == 1
        assert df["subject"][0] == "01"
        assert df["session"][0] == "02"
        assert df["task"][0] == "nback"
        assert df["run"][0] == "01"


@pytest.mark.ai_generated
def test_repr(mock_bids_dataset: Path) -> None:
    """Test string representation."""
    with BIDSDuckDBLoader(mock_bids_dataset) as loader:
        loader.load_participants()
        repr_str = repr(loader)

        assert "BIDSDuckDBLoader" in repr_str
        assert str(mock_bids_dataset.resolve()) in repr_str
        assert "participants" in repr_str
