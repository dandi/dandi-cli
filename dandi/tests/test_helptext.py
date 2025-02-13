import subprocess


def get_helptext(command):
    result = subprocess.run(
        [*command, '--help'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    return result.stdout


def test_resource_identifier_helptext():
    # The \n chars must be included for correct rendering
    correct = "Accepted resource identifier patterns:\n   - DANDI:<dandiset id>[/<version>]\n"

    ls_helptext = get_helptext(['dandi', 'ls'])
    assert correct in ls_helptext

    download_helptext = get_helptext(['dandi', 'download'])
    assert correct in download_helptext
