from pathlib import Path

from click.testing import CliRunner
import pytest

from ..cmd_digest import digest


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
