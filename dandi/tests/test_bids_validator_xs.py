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
