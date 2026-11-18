"""Phase F0 integration test (IMPL-API-001 §4): the stack works end to end.

Migrations run as the maintenance role, /healthz answers as the app role, and one presigned POST round trip
goes through the DEC-047 server into the private bucket.
"""

from __future__ import annotations

import http.client
import uuid
from typing import Any
from urllib.parse import urlsplit

import pytest
from django.core.management import call_command
from django.db import connections
from django.test import Client

from tests.integration.stack import S3_BUCKET, s3_client

pytestmark = pytest.mark.integration


def _post_form(url: str, fields: dict[str, str], content: bytes, content_type: str) -> int:
    boundary = uuid.uuid4().hex
    parts = [
        f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n'.encode()
        for key, value in fields.items()
    ]
    parts.append(
        f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="photo.jpg"\r\n'
        f"Content-Type: {content_type}\r\n\r\n".encode()
        + content
        + f"\r\n--{boundary}--\r\n".encode()
    )
    target = urlsplit(url)
    connection = http.client.HTTPConnection(target.netloc, timeout=10)
    connection.request(
        "POST", target.path, b"".join(parts), {"Content-Type": f"multipart/form-data; boundary={boundary}"}
    )
    status = connection.getresponse().status
    connection.close()
    return status


@pytest.mark.req("REQ-N-OPS-01")
@pytest.mark.django_db(databases=["default", "maintenance"])
def test_phase0_stack_end_to_end(client: Client) -> None:
    call_command("migrate", database="maintenance", verbosity=0)
    with connections["maintenance"].cursor() as cursor:
        cursor.execute("SELECT current_user")
        assert cursor.fetchone() == ("cherrylove_maintenance",)

    with connections["default"].cursor() as cursor:
        cursor.execute("SELECT current_user")
        assert cursor.fetchone() == ("cherrylove_app",)
    assert client.get("/healthz").status_code == 200

    storage: Any = s3_client()
    key = f"quarantine/{uuid.uuid4()}/{uuid.uuid4()}"
    post = storage.generate_presigned_post(
        Bucket=S3_BUCKET,
        Key=key,
        Fields={"Content-Type": "image/jpeg"},
        Conditions=[{"Content-Type": "image/jpeg"}, ["content-length-range", 1, 20 * 1024 * 1024]],
        ExpiresIn=900,
    )
    content = b"\xff\xd8\xff" + b"0" * 1021
    assert _post_form(post["url"], post["fields"], content, "image/jpeg") in (200, 201, 204)
    try:
        assert storage.get_object(Bucket=S3_BUCKET, Key=key)["Body"].read() == content
    finally:
        storage.delete_object(Bucket=S3_BUCKET, Key=key)
