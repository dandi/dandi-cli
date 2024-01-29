# emacs: -*- mode: python; py-indent-offset: 4; tab-width: 4; indent-tabs-mode: nil -*-
# ex: set sts=4 ts=4 sw=4 noet:
# ## ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ##
#
#   See COPYING file distributed along with the dandi package for the
#   copyright and license terms.
#
# ## ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ##

from pathlib import Path

from pytest_mock import MockerFixture

from .. import digests
from ..digests import Digester, get_zarr_checksum


def test_digester(tmp_path):
    digester = Digester()

    f = tmp_path / "sample.txt"
    f.write_bytes(b"123")
    assert digester(f) == {
        "md5": "202cb962ac59075b964b07152d234b70",
        "sha1": "40bd001563085fc35165329ea1ff5c5ecbdbbeef",
        "sha256": "a665a45920422f9d417e4867efdc4fb8a04a1f3fff1fa07e998e86f7f7a27ae3",
        "sha512": "3c9909afec25354d551dae21590bb26e38d53f2173b8d3dc3eee4c047e7a"
        "b1c1eb8b85103e3be7ba613b31bb5c9c36214dc9f14a42fd7a2fdb84856b"
        "ca5c44c2",
    }

    f = tmp_path / "0"
    f.write_bytes(chr(0).encode())
    assert digester(f) == {
        "md5": "93b885adfe0da089cdf634904fd59f71",
        "sha1": "5ba93c9db0cff93f52b521d7420e43f6eda2784f",
        "sha256": "6e340b9cffb37a989ca544e6bb780a2c78901d3fb33738768511a30617afa01d",
        "sha512": "b8244d028981d693af7b456af8efa4cad63d282e19ff14942c246e50d935"
        "1d22704a802a71c3580b6370de4ceb293c324a8423342557d4e5c38438f0"
        "e36910ee",
    }

    f = tmp_path / "long.txt"
    f.write_bytes(b"123abz\n" * 1000000)
    assert digester(f) == {
        "md5": "81b196e3d8a1db4dd2e89faa39614396",
        "sha1": "5273ac6247322c3c7b4735a6d19fd4a5366e812f",
        "sha256": "80028815b3557e30d7cbef1d8dbc30af0ec0858eff34b960d2839fd88ad08871",
        "sha512": "684d23393eee455f44c13ab00d062980937a5d040259d69c6b291c983bf6"
        "35e1d405ff1dc2763e433d69b8f299b3f4da500663b813ce176a43e29ffc"
        "c31b0159",
    }


def test_get_zarr_checksum(mocker: MockerFixture, tmp_path: Path) -> None:
    # Use write_bytes() so that the line endings are the same on POSIX and
    # Windows.
    (tmp_path / "file1.txt").write_bytes(b"This is the first file.\n")
    (tmp_path / "file2.txt").write_bytes(b"This is the second file.\n")
    sub1 = tmp_path / "sub1"
    sub1.mkdir()
    (sub1 / "file3.txt").write_bytes(b"This is the third file.\n")
    (sub1 / "file4.txt").write_bytes(b"This is the fourth file.\n")
    (sub1 / "file5.txt").write_bytes(b"This is the fifth file.\n")
    subsub = sub1 / "subsub"
    subsub.mkdir()
    (subsub / "file6.txt").write_bytes(b"This is the sixth file.\n")
    sub2 = tmp_path / "sub2"
    sub2.mkdir()
    (sub2 / "file7.txt").write_bytes(b"This is the seventh file.\n")
    (sub2 / "file8.txt").write_bytes(b"This is the eighth file.\n")
    empty = tmp_path / "empty"
    empty.mkdir()

    assert (
        get_zarr_checksum(tmp_path / "file1.txt") == "d0aa42f003e36c1ecaf9aa8f20b6f1ad"
    )
    assert get_zarr_checksum(tmp_path) == "25627e0fc7c609d10100d020f7782a25-8--197"
    assert get_zarr_checksum(sub1) == "64af93ad7f8d471c00044d1ddbd4c0ba-4--97"

    assert get_zarr_checksum(empty) == "481a2f77ab786a0f45aafd5db0971caa-0--0"

    spy = mocker.spy(digests, "md5file_nocache")
    assert (
        get_zarr_checksum(
            tmp_path,
            known={
                "file1.txt": "9ee7a152c5adb60803c928733acc1533",
                # ^^ This one is different!
                "file2.txt": "340c108ee69bf4626e7995a7048f52b8",
                "sub1/file3.txt": "7351dc767bfad322ddce50401badc359",
                "sub1/file4.txt": "bbede70f39fa8fc34f2dc4eda8b6bdea",
                "sub1/file5.txt": "c4e828c509f90b84e5b72d9d5612d676",
                "sub1/subsub/file6.txt": "6a7fe3b9e2c69a54216b7d5dcb4fe61d",
                # "sub2/file7.txt": Absent!
                "sub2/file8.txt": "7aadbff2b21f438baccded18b2e81ae3",
                "nonexistent-file.txt": "123456789012345678901234567890ab",
                # ^^ Not used in calculation!
            },
        )
        == "f77f4c5b277575f781c19ba91422f0c5-8--197"
    )
    spy.assert_called_once_with(sub2 / "file7.txt")
