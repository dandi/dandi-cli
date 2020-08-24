from ..models import DandiMeta, AssetMeta


def test_dandiset():
    assert DandiMeta.unvalidated()


def test_asset():
    assert AssetMeta.unvalidated()
