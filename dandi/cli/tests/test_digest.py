import os
from pathlib import Path
import subprocess

from click.testing import CliRunner
import numpy as np
import pytest
import zarr

from ..cmd_digest import digest
from ...tests.test_helpers import zarr_format_of

# The on-disk Zarr serialisation format changed between V2 (``.zgroup`` /
# ``.zarray``) and V3 (``zarr.json``, ``c/<chunk>`` layout, different default
# compressor), so the digest of "the same" Zarr data differs. Key expected
# values on the format that was *actually* produced rather than on
# ``zarr.__version__`` — zarr-python 3.x can still write V2 via
# ``zarr_format=2``.
_EXPECTED_SAMPLE_ZARR_DIGEST_BY_FORMAT = {
    "2": "4313ab36412db2981c3ed391b38604d6-5--1516",
    "3": "00157f091c9a6295e89eb3c4c2efaeff-5--3935",
}


def test_digest_default():
    runner = CliRunner()
    with runner.isolated_filesystem():
        Path("file.txt").write_bytes(b"123")
        r = runner.invoke(digest, ["file.txt"])
        assert r.exit_code == 0
        assert r.output == "file.txt: d022646351048ac0ba397d12dfafa304-1\n"


@pytest.mark.parametrize(
    "alg,filehash",
    [
        ("md5", "202cb962ac59075b964b07152d234b70"),
        ("zarr-checksum", "202cb962ac59075b964b07152d234b70"),
        ("sha1", "40bd001563085fc35165329ea1ff5c5ecbdbbeef"),
        ("sha256", "a665a45920422f9d417e4867efdc4fb8a04a1f3fff1fa07e998e86f7f7a27ae3"),
        (
            "sha512",
            "3c9909afec25354d551dae21590bb26e38d53f2173b8d3dc3eee4c047e7a"
            "b1c1eb8b85103e3be7ba613b31bb5c9c36214dc9f14a42fd7a2fdb84856b"
            "ca5c44c2",
        ),
    ],
)
def test_digest(alg, filehash):
    runner = CliRunner()
    with runner.isolated_filesystem():
        Path("file.txt").write_bytes(b"123")
        r = runner.invoke(digest, ["--digest", alg, "file.txt"])
        assert r.exit_code == 0
        assert r.output == f"file.txt: {filehash}\n"


def test_digest_zarr():
    # Expected digest is selected by the Zarr serialisation format that
    # ``zarr.save`` actually produced (V2 vs V3 layouts have different digests).
    runner = CliRunner()
    with runner.isolated_filesystem():
        dt = np.dtype("<i8")
        zarr.save(
            "sample.zarr", np.arange(1000, dtype=dt), np.arange(1000, 0, -1, dtype=dt)
        )
        expected = _EXPECTED_SAMPLE_ZARR_DIGEST_BY_FORMAT[
            zarr_format_of(Path("sample.zarr"))
        ]
        r = runner.invoke(digest, ["--digest", "zarr-checksum", "sample.zarr"])
        assert r.exit_code == 0
        assert r.output == f"sample.zarr: {expected}\n"


def test_digest_empty_zarr(tmp_path: Path) -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        os.mkdir("empty.zarr")
        r = runner.invoke(digest, ["--digest", "zarr-checksum", "empty.zarr"])
        assert r.exit_code == 0
        assert r.output == "empty.zarr: 481a2f77ab786a0f45aafd5db0971caa-0--0\n"


def test_digest_zarr_with_excluded_dotfiles():
    # See comment in `test_digest_zarr` regarding V2 vs V3 serialisation.
    runner = CliRunner()
    with runner.isolated_filesystem():
        dt = np.dtype("<i8")
        zarr.save(
            "sample.zarr", np.arange(1000, dtype=dt), np.arange(1000, 0, -1, dtype=dt)
        )
        expected = _EXPECTED_SAMPLE_ZARR_DIGEST_BY_FORMAT[
            zarr_format_of(Path("sample.zarr"))
        ]
        subprocess.run(["git", "init"], cwd="sample.zarr", check=True)
        os.mkdir("sample.zarr/.dandi")
        Path("sample.zarr", ".dandi", "somefile.txt").touch()
        Path("sample.zarr", ".gitattributes").touch()
        Path("sample.zarr", "arr_0", ".gitmodules").touch()
        Path("sample.zarr", "arr_1", ".datalad").mkdir()
        Path("sample.zarr", "arr_1", ".datalad", "config").touch()
        r = runner.invoke(digest, ["--digest", "zarr-checksum", "sample.zarr"])
        assert r.exit_code == 0
        assert r.output == f"sample.zarr: {expected}\n"
