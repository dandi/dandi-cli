import os


def test_validate_bids(bids_examples):
    from dandi.validate import validate_bids

    whitelist = [
        "qmri_megre",
        "asl003",
        "pet002",
        "asl005",
        "asl002",
        "pet004",
        "eeg_cbm",
        "pet005",
        "hcp_example_bids",
        "asl004",
        "qmri_tb1tfl",
        "micr_SPIM",
        "pet001",
        "pet003",
        "micr_SEM",
        "micr_SEM-dandi",
    ]
    schema_path = "{module_path}/support/bids/schemadata/1.7.0+012+dandi001"

    # Validate per dataset, with debugging:
    for i in os.listdir(bids_examples):
        if i in whitelist:
            result = validate_bids(
                os.path.join(bids_examples, i), schema_version=schema_path
            )
            # Have all files been validated?
            assert len(result["path_tracking"]) == 0
