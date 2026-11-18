"""The local Compose stack is up with the pinned services (REQ-N-OPS-01, DEC-047).

Endpoints come from env vars with compose.yaml defaults, so CI service containers can reuse the test.
"""

from __future__ import annotations

import json
import os
import smtplib
import socket
import urllib.parse
import urllib.request
import uuid
from email.message import EmailMessage
from typing import Any

import boto3
import pytest
from botocore import UNSIGNED
from botocore.client import Config
from django.db import connection

from tests.integration.stack import S3_BUCKET, s3_client, s3_endpoint

pytestmark = pytest.mark.integration

REDIS = (os.environ.get("REDIS_HOST", "127.0.0.1"), int(os.environ.get("REDIS_PORT", "6379")))
SMTP = (os.environ.get("SMTP_HOST", "127.0.0.1"), int(os.environ.get("SMTP_PORT", "1025")))
MAILPIT_API = os.environ.get("MAILPIT_API", "http://127.0.0.1:8025")


@pytest.mark.req("REQ-N-OPS-01")
@pytest.mark.django_db
def test_postgresql_is_the_pinned_version() -> None:
    with connection.cursor() as cursor:
        cursor.execute("SHOW server_version")
        row = cursor.fetchone()
    assert row is not None
    assert row[0].startswith("18.7")


@pytest.mark.req("REQ-N-OPS-01")
def test_redis_answers_ping_and_is_the_pinned_version() -> None:
    with socket.create_connection(REDIS, timeout=5) as sock:
        sock.sendall(b"PING\r\nINFO server\r\n")
        reply = b""
        while b"redis_version" not in reply or not reply.endswith(b"\r\n"):
            reply += sock.recv(4096)
    assert reply.startswith(b"+PONG")
    assert b"redis_version:8.8.4" in reply


@pytest.mark.req("REQ-N-OPS-01")
def test_storage_bucket_exists() -> None:
    client: Any = s3_client()
    client.head_bucket(Bucket=S3_BUCKET)


@pytest.mark.req("REQ-N-OPS-01")
def test_storage_bucket_is_private() -> None:
    anonymous: Any = boto3.client(
        "s3",
        endpoint_url=s3_endpoint(),
        region_name="us-east-1",
        config=Config(signature_version=UNSIGNED),
    )
    with pytest.raises(anonymous.exceptions.ClientError) as denied:
        anonymous.list_objects_v2(Bucket=S3_BUCKET)
    assert denied.value.response["ResponseMetadata"]["HTTPStatusCode"] in (401, 403)


@pytest.mark.req("REQ-N-OPS-01")
def test_sent_mail_appears_in_mailpit() -> None:
    subject = f"stack-check-{uuid.uuid4()}"
    message = EmailMessage()
    message["From"] = "noreply@cherrylove.local"
    message["To"] = "partner@cherrylove.local"
    message["Subject"] = subject
    message.set_content("Local stack check.")
    with smtplib.SMTP(*SMTP, timeout=5) as smtp:
        smtp.send_message(message)

    query = urllib.parse.quote(f'subject:"{subject}"')
    with urllib.request.urlopen(f"{MAILPIT_API}/api/v1/search?query={query}", timeout=5) as response:
        found = json.load(response)
    assert found["messages_count"] == 1
