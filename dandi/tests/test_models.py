from ..models import Dandiset, Asset


def test_dandiset():
    assert Dandiset.unvalidated()


def test_asset():
    assert Asset.unvalidated()
