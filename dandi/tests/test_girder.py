import pytest
from ..exceptions import LockingError
from .. import girder


def test_lock_dandiset(local_docker_compose_env):
    DANDISET_ID = "000001"
    client = girder.get_client(local_docker_compose_env["instance"].girder)
    resp = client.get(f"dandi/{DANDISET_ID}/lock/owner")
    assert resp is None
    with client.lock_dandiset(DANDISET_ID):
        resp = client.get(f"dandi/{DANDISET_ID}/lock/owner")
        assert resp is not None
    resp = client.get(f"dandi/{DANDISET_ID}/lock/owner")
    assert resp is None


def test_lock_dandiset_error_on_nest(local_docker_compose_env):
    DANDISET_ID = "000001"
    client = girder.get_client(local_docker_compose_env["instance"].girder)
    with client.lock_dandiset(DANDISET_ID):
        with pytest.raises(LockingError) as excinfo:
            with client.lock_dandiset(DANDISET_ID):
                raise AssertionError("This shouldn't be reached")  # pragma: no cover
        assert str(excinfo.value) == f"Failed to lock dandiset {DANDISET_ID}"


def test_lock_dandiset_unlock_within(local_docker_compose_env):
    DANDISET_ID = "000001"
    client = girder.get_client(local_docker_compose_env["instance"].girder)
    unlocked = False
    with pytest.raises(LockingError) as excinfo:
        with client.lock_dandiset(DANDISET_ID):
            client.post(f"dandi/{DANDISET_ID}/unlock")
            unlocked = True
    assert unlocked
    assert str(excinfo.value) == f"Failed to unlock dandiset {DANDISET_ID}"
