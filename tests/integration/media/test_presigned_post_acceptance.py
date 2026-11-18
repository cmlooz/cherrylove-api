"""Presigned POST acceptance test against the local S3 server (DEC-037 spike, DEC-047: Versity).

Every case below is a rule from ADR-007 §2 (storage itself enforces size and type)
and §7 (private bucket, CORS for one origin, short signed GET). The F0.1 spike ran it
against four candidates; since F0.4 it runs against the server chosen in DEC-047.
In F4.1 these cases become the integration tests of the S3 adapter.
"""

from __future__ import annotations

import http.client
import time
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

import pytest

from tests.integration.stack import s3_client, s3_endpoint

pytestmark = pytest.mark.integration

WEB_ORIGIN = "http://localhost:5173"
OTHER_ORIGIN = "http://evil.example"
MAX_BYTES = 1024
CONTENT_TYPE = "image/jpeg"


@dataclass(frozen=True)
class Response:
    status: int
    headers: dict[str, str]
    body: bytes


def _request(method: str, url: str, body: bytes = b"", headers: dict[str, str] | None = None) -> Response:
    """Plain HTTP call that never raises on 4xx (status is the assertion)."""
    parts = urlsplit(url)
    conn = http.client.HTTPConnection(parts.netloc, timeout=10)
    path = parts.path + (f"?{parts.query}" if parts.query else "")
    conn.request(method, path or "/", body=body, headers=headers or {})
    raw = conn.getresponse()
    result = Response(raw.status, {k.lower(): v for k, v in raw.getheaders()}, raw.read())
    conn.close()
    return result


def _multipart(fields: dict[str, str], content: bytes, content_type: str) -> tuple[bytes, str]:
    boundary = uuid.uuid4().hex
    lines: list[bytes] = []
    for key, value in fields.items():
        lines += [
            f"--{boundary}".encode(),
            f'Content-Disposition: form-data; name="{key}"'.encode(),
            b"",
            value.encode(),
        ]
    lines += [
        f"--{boundary}".encode(),
        b'Content-Disposition: form-data; name="file"; filename="upload.bin"',
        f"Content-Type: {content_type}".encode(),
        b"",
        content,
        f"--{boundary}--".encode(),
        b"",
    ]
    return b"\r\n".join(lines), f"multipart/form-data; boundary={boundary}"


@dataclass
class Storage:
    endpoint: str
    client: Any
    bucket: str

    def presigned_post(self, key: str, *, expires_in: int = 900, content_type: str = CONTENT_TYPE) -> dict[str, Any]:
        post: dict[str, Any] = self.client.generate_presigned_post(
            Bucket=self.bucket,
            Key=key,
            Fields={"Content-Type": content_type},
            Conditions=[
                {"Content-Type": content_type},
                ["content-length-range", 1, MAX_BYTES],
            ],
            ExpiresIn=expires_in,
        )
        return post

    def upload(self, post: dict[str, Any], content: bytes, *, content_type: str = CONTENT_TYPE) -> Response:
        fields = dict(post["fields"])
        fields["Content-Type"] = content_type
        body, header = _multipart(fields, content, content_type)
        return _request("POST", post["url"], body, {"Content-Type": header})

    def exists(self, key: str) -> bool:
        listed = self.client.list_objects_v2(Bucket=self.bucket, Prefix=key)
        return any(item["Key"] == key for item in listed.get("Contents", []))


@pytest.fixture
def storage() -> Iterator[Storage]:
    client = s3_client()
    bucket = f"acceptance-{uuid.uuid4().hex[:12]}"
    client.create_bucket(Bucket=bucket)
    yield Storage(s3_endpoint(), client, bucket)
    for item in client.list_objects_v2(Bucket=bucket).get("Contents", []):
        client.delete_object(Bucket=bucket, Key=item["Key"])
    client.delete_bucket(Bucket=bucket)


def _key() -> str:
    return f"quarantine/{uuid.uuid4()}/{uuid.uuid4()}"


@pytest.mark.req("REQ-N-SEC-06")
def test_valid_upload_is_accepted(storage: Storage) -> None:
    key = _key()
    response = storage.upload(storage.presigned_post(key), b"x" * 512)
    assert response.status in (200, 201, 204), response.body
    assert storage.exists(key)


@pytest.mark.req("REQ-N-SEC-06")
@pytest.mark.parametrize("size", [0, MAX_BYTES + 1], ids=["empty", "too_large"])
def test_size_outside_content_length_range_is_rejected_by_storage(storage: Storage, size: int) -> None:
    key = _key()
    response = storage.upload(storage.presigned_post(key), b"x" * size)
    assert 400 <= response.status < 500, response.status
    assert not storage.exists(key)


@pytest.mark.req("REQ-N-SEC-06")
def test_wrong_content_type_is_rejected(storage: Storage) -> None:
    key = _key()
    response = storage.upload(storage.presigned_post(key), b"x" * 512, content_type="text/html")
    assert 400 <= response.status < 500, response.status
    assert not storage.exists(key)


@pytest.mark.req("REQ-N-SEC-06")
def test_expired_policy_is_rejected(storage: Storage) -> None:
    key = _key()
    post = storage.presigned_post(key, expires_in=1)
    time.sleep(3)
    response = storage.upload(post, b"x" * 512)
    assert 400 <= response.status < 500, response.status
    assert not storage.exists(key)


@pytest.mark.req("REQ-N-SEC-06")
def test_signed_get_works_then_expires(storage: Storage) -> None:
    key = _key()
    storage.client.put_object(Bucket=storage.bucket, Key=key, Body=b"payload")
    url = storage.client.generate_presigned_url(
        "get_object", Params={"Bucket": storage.bucket, "Key": key}, ExpiresIn=2
    )
    first = _request("GET", url)
    assert first.status == 200
    assert first.body == b"payload"
    time.sleep(4)
    assert 400 <= _request("GET", url).status < 500


@pytest.mark.req("REQ-N-SEC-06")
def test_bucket_cors_allows_only_the_web_origin(storage: Storage) -> None:
    storage.client.put_bucket_cors(
        Bucket=storage.bucket,
        CORSConfiguration={
            "CORSRules": [
                {
                    "AllowedOrigins": [WEB_ORIGIN],
                    "AllowedMethods": ["POST", "GET"],
                    "AllowedHeaders": ["*"],
                    "MaxAgeSeconds": 600,
                }
            ]
        },
    )
    url = f"{storage.endpoint}/{storage.bucket}"

    def preflight(origin: str) -> Response:
        return _request(
            "OPTIONS",
            url,
            headers={"Origin": origin, "Access-Control-Request-Method": "POST"},
        )

    allowed = preflight(WEB_ORIGIN)
    assert allowed.headers.get("access-control-allow-origin") == WEB_ORIGIN, allowed.headers
    denied = preflight(OTHER_ORIGIN)
    assert "access-control-allow-origin" not in denied.headers, denied.headers


@pytest.mark.req("REQ-N-SEC-06")
def test_bucket_is_private_by_default(storage: Storage) -> None:
    key = _key()
    storage.client.put_object(Bucket=storage.bucket, Key=key, Body=b"secret")
    base = f"{storage.endpoint}/{storage.bucket}"
    assert _request("GET", f"{base}/{key}").status in (401, 403)
    assert _request("GET", f"{base}?list-type=2").status in (401, 403)
