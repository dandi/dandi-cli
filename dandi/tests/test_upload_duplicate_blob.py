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


def _http_409(location: str | None = None) -> requests.HTTPError:
    resp = requests.Response()
    resp.status_code = 409
    if location is not None:
        resp.headers["Location"] = location
    return requests.HTTPError("409", response=resp)


class FakeClient:
    """
    Fake API client simulating a race: the blob does not exist at
    ``/uploads/initialize/`` on the first call, but by the time we call
    ``/uploads/{id}/validate/`` an identical blob was created by a concurrent
    upload, so validate returns 409 without a blob id.
    """

    def __init__(self, filetag: str, size: int) -> None:
        self.filetag = filetag
        self.size = size
        self.init_calls = 0
        self.posts: list[str] = []

    def post(self, path: str, **kwargs: Any) -> Any:
        self.posts.append(path)
        if path == "/uploads/initialize/":
            self.init_calls += 1
            if self.init_calls == 1:
                return {
                    "upload_id": UPLOAD_ID,
                    "parts": [
                        {"part_number": 1, "size": self.size, "upload_url": PART_URL}
                    ],
                }
            raise _http_409(BLOB_ID)
        if path == f"/uploads/{UPLOAD_ID}/complete/":
            return {"complete_url": COMPLETE_URL, "body": "<x/>"}
        if path == f"/uploads/{UPLOAD_ID}/validate/":
            raise _http_409()
        assert path == "/dandisets/000001/versions/draft/assets/"
        assert kwargs["json"]["blob_id"] == BLOB_ID
        return {"asset_id": "a" * 8}


@pytest.mark.ai_generated
@responses.activate
def test_iter_upload_validate_409_uses_existing_blob(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    p = tmp_path / "f.bin"
    p.write_bytes(b"some content")
    etagger = get_dandietag(p)
    client = FakeClient(etagger.as_str(), p.stat().st_size)
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
    statuses = list(asset.iter_upload(dandiset, {}))
    assert statuses[-1]["status"] == "done"
    assert client.init_calls == 2
