from pathlib import Path

METADATA_DIR = Path(__file__).with_name("data") / "metadata"


def test__add_entity():
    from dandi.bids_validator_xs import _add_entity

    # Test empty input and directory creation and required entity
    regex_entities = ""
    entity = "subject"
    entity_shorthand = "sub"
    variable_field = "([a-z,A-Z,0-9]*?)"
    requirement_level = "required"

    _regex_entities = _add_entity(
        regex_entities,
        entity,
        entity_shorthand,
        variable_field,
        requirement_level,
    )

    assert _regex_entities == "sub-(?P=subject)"

    # Test append input and optional entity
    regex_entities = (
        "sub-(?P=subject)(|_ses-(?P=session))"
        "(|_task-(?P<task>([a-z,A-Z,0-9]*?)))(|_trc-(?P<tracer>([a-z,A-Z,0-9]*?)))"
        "(|_rec-(?P<reconstruction>([a-z,A-Z,0-9]*?)))"
        "(|_run-(?P<run>([a-z,A-Z,0-9]*?)))"
    )
    entity = "recording"
    entity_shorthand = "recording"
    variable_field = "([a-z,A-Z,0-9]*?)"
    requirement_level = "optional"

    _regex_entities = _add_entity(
        regex_entities,
        entity,
        entity_shorthand,
        variable_field,
        requirement_level,
    )

    assert (
        _regex_entities == "sub-(?P=subject)(|_ses-(?P=session))"
        "(|_task-(?P<task>([a-z,A-Z,0-9]*?)))(|_trc-(?P<tracer>([a-z,A-Z,0-9]*?)))"
        "(|_rec-(?P<reconstruction>([a-z,A-Z,0-9]*?)))"
        "(|_run-(?P<run>([a-z,A-Z,0-9]*?)))"
        "(|_recording-(?P<recording>([a-z,A-Z,0-9]*?)))"
    )


def test__add_extensions():
    from dandi.bids_validator_xs import _add_extensions

    # Test single extension
    regex_string = (
        "sub-(?P=subject)(|_ses-(?P=session))"
        "_sample-(?P<sample>([a-z,A-Z,0-9]*?))"
        "(|_acq-(?P<acquisition>([a-z,A-Z,0-9]*?)))_photo"
    )
    variant = {
        "suffixes": ["photo"],
        "extensions": [".jpg"],
        "entities": {
            "subject": "required",
            "session": "optional",
            "sample": "required",
            "acquisition": "optional",
        },
    }
    _regex_string = _add_extensions(regex_string, variant)

    assert (
        _regex_string == "sub-(?P=subject)(|_ses-(?P=session))"
        "_sample-(?P<sample>([a-z,A-Z,0-9]*?))"
        "(|_acq-(?P<acquisition>([a-z,A-Z,0-9]*?)))_photo\\.jpg"
    )

    # Test multiple extensions
    regex_string = (
        "sub-(?P=subject)(|_ses-(?P=session))"
        "_sample-(?P<sample>([a-z,A-Z,0-9]*?))"
        "(|_acq-(?P<acquisition>([a-z,A-Z,0-9]*?)))_photo"
    )
    variant = {
        "suffixes": ["photo"],
        "extensions": [".jpg", ".png", ".tif"],
        "entities": {
            "subject": "required",
            "session": "optional",
            "sample": "required",
            "acquisition": "optional",
        },
    }
    _regex_string = _add_extensions(regex_string, variant)

    assert (
        _regex_string == "sub-(?P=subject)(|_ses-(?P=session))"
        "_sample-(?P<sample>([a-z,A-Z,0-9]*?))"
        "(|_acq-(?P<acquisition>([a-z,A-Z,0-9]*?)))_photo\\.(jpg|png|tif)"
    )


def test__add_subdirs():
    from dandi.bids_validator_xs import _add_subdirs

    regex_string = "sub-(?P=subject)_sessions\\.(tsv|json)"
    variant = {
        "suffixes": ["sessions"],
        "extensions": [".tsv", ".json"],
        "entities": {"subject": "required"},
    }
    datatype = "tabular_metadata"
    entity_definitions = {
        "acquisition": {
            "name": "Acquisition",
            "entity": "acq",
            "type": "string",
            "format": "label",
        },
        "session": {
            "name": "Session",
            "entity": "ses",
            "type": "string",
            "format": "label",
        },
        "subject": {
            "name": "Subject",
            "entity": "sub",
            "type": "string",
            "format": "label",
        },
    }
    modality_datatypes = [
        "anat",
        "dwi",
        "fmap",
        "func",
        "perf",
        "eeg",
        "ieeg",
        "meg",
        "beh",
        "pet",
        "micr",
    ]
    _regex_string = _add_subdirs(
        regex_string, variant, datatype, entity_definitions, modality_datatypes
    )

    assert (
        _regex_string == "/sub-(?P<subject>([a-z,A-Z,0-9]*?))/sub-(?P=subject)"
        "_sessions\\.(tsv|json)"
    )


def test__add_suffixes():
    from dandi.bids_validator_xs import _add_suffixes

    # Test single expansion
    regex_entities = "sub-(?P=subject)"
    variant = {
        "suffixes": ["sessions"],
        "extensions": [
            ".tsv",
            ".json",
        ],
        "entities": {"subject": "required"},
    }
    regex_string = "sub-(?P=subject)_sessions"

    _regex_string = _add_suffixes(regex_entities, variant)

    assert _regex_string == regex_string

    # Test multiple expansions
    regex_entities = (
        "sub-(?P=subject)(|_ses-(?P=session))"
        "(|_acq-(?P<acquisition>([a-z,A-Z,0-9]*?)))"
        "(|_rec-(?P<reconstruction>([a-z,A-Z,0-9]*?)))"
        "(|_dir-(?P<direction>([a-z,A-Z,0-9]*?)))(|_run-(?P<run>([a-z,A-Z,0-9]*?)))"
        "(|_recording-(?P<recording>([a-z,A-Z,0-9]*?)))"
    )
    variant = {
        "suffixes": [
            "physio",
            "stim",
        ],
        "extensions": [
            ".tsv.gz",
            ".json",
        ],
        "entities": {
            "subject": "required",
            "session": "optional",
            "acquisition": "optional",
            "reconstruction": "optional",
            "direction": "optional",
            "run": "optional",
            "recording": "optional",
        },
    }
    regex_string = (
        "sub-(?P=subject)(|_ses-(?P=session))"
        "(|_acq-(?P<acquisition>([a-z,A-Z,0-9]*?)))"
        "(|_rec-(?P<reconstruction>([a-z,A-Z,0-9]*?)))"
        "(|_dir-(?P<direction>([a-z,A-Z,0-9]*?)))(|_run-(?P<run>([a-z,A-Z,0-9]*?)))"
        "(|_recording-(?P<recording>([a-z,A-Z,0-9]*?)))"
        "_(physio|stim)"
    )

    _regex_string = _add_suffixes(regex_entities, variant)

    assert _regex_string == regex_string
