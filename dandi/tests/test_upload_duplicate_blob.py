from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest
import requests
import responses

from ..files import LocalFileAsset
from ..support.digests import get_dandietag

BLOB_ID = "existing-blob-id"
UPLOAD_ID = "the-upload-id"
PART_URL = "http://storage.test/part1"
COMPLETE_URL = "http://storage.test/complete"


def _http_error(status: int, location: str | None = None) -> requests.HTTPError:
    resp = requests.Response()
    resp.status_code = status
    if location is not None:
        resp.headers["Location"] = location
    return requests.HTTPError(str(status), response=resp)


class FakeClient:
    """
    Fake API client simulating a race: the blob does not exist at
    ``/uploads/initialize/`` on the first call, but by the time we call
    ``/uploads/{id}/validate/`` an identical blob was created by a concurrent
    upload, so validate returns 409 without a blob id.
    """

    def __init__(self, size: int, scenario: str) -> None:
        self.size = size
        self.scenario = scenario
        self.init_payloads: list[Any] = []
        self.init_calls = 0
        self.posts: list[str] = []

    def post(self, path: str, **kwargs: Any) -> Any:
        self.posts.append(path)
        if path == "/uploads/initialize/":
            self.init_calls += 1
            self.init_payloads.append(kwargs["json"])
            if self.init_calls == 1:
                return {
                    "upload_id": UPLOAD_ID,
                    "parts": [
                        {"part_number": 1, "size": self.size, "upload_url": PART_URL}
                    ],
                }
            if self.scenario == "no_blob":
                return {"upload_id": "another", "parts": []}
            raise _http_error(409, BLOB_ID if self.scenario != "no_location" else None)
        if path == f"/uploads/{UPLOAD_ID}/complete/":
            return {"complete_url": COMPLETE_URL, "body": "<x/>"}
        if path == f"/uploads/{UPLOAD_ID}/validate/":
            if self.scenario == "validate_500":
                raise _http_error(500)
            raise _http_error(
                409, BLOB_ID if self.scenario == "validate_location" else None
            )
        assert path == "/dandisets/000001/versions/draft/assets/"
        assert kwargs["json"]["blob_id"] == BLOB_ID
        return {"asset_id": "a" * 8}


@pytest.mark.ai_generated
@pytest.mark.parametrize(
    "scenario,status,init_calls",
    [
        ("lookup", None, 2),
        ("validate_location", None, 1),
        ("no_blob", 409, 2),
        ("no_location", 409, 2),
        ("validate_500", 500, 1),
    ],
)
@responses.activate
def test_iter_upload_validate_409(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    scenario: str,
    status: int | None,
    init_calls: int,
) -> None:
    p = tmp_path / "f.bin"
    p.write_bytes(b"some content")
    etagger = get_dandietag(p)
    client = FakeClient(p.stat().st_size, scenario)
    dandiset = Mock(identifier="000001", client=client)
    dandiset.version_api_path = "/dandisets/000001/versions/draft/"
    responses.add(
        responses.PUT,
        PART_URL,
        headers={"ETag": f'"{etagger.get_part_etag(etagger.get_part(1))}"'},
    )
    responses.add(responses.POST, COMPLETE_URL, body="<x/>")
    monkeypatch.setattr(
        "dandi.files.bases.RemoteAsset.from_data", lambda ds, data: data
    )
    asset = LocalFileAsset(filepath=p, path="f.bin", dandiset_path=tmp_path)
    if status is None:
        statuses = list(asset.iter_upload(dandiset, {}))
        assert statuses[-1]["status"] == "done"
    else:
        with pytest.raises(requests.HTTPError) as excinfo:
            list(asset.iter_upload(dandiset, {}))
        # the original validate error must be what propagates
        assert excinfo.value.response.status_code == status
        assert f"/uploads/{UPLOAD_ID}/validate/" in client.posts
    assert client.init_calls == init_calls
    # any re-initialization must use the very same payload
    assert all(pl == client.init_payloads[0] for pl in client.init_payloads)
