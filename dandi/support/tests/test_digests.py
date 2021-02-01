# emacs: -*- mode: python; py-indent-offset: 4; tab-width: 4; indent-tabs-mode: nil -*-
# ex: set sts=4 ts=4 sw=4 noet:
# ## ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ##
#
#   See COPYING file distributed along with the dandi package for the
#   copyright and license terms.
#
# ## ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ##

from ..digests import Digester


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
