"""Connection details of the local stack (compose.yaml defaults, overridable by env vars)."""

from __future__ import annotations

import os
from typing import Any

import boto3
from botocore.client import Config

S3_BUCKET = os.environ.get("S3_BUCKET", "cherrylove-media")


def s3_endpoint() -> str:
    return os.environ.get("S3_ENDPOINT", "http://127.0.0.1:7070")


def s3_client() -> Any:
    return boto3.client(
        "s3",
        endpoint_url=s3_endpoint(),
        aws_access_key_id=os.environ.get("S3_ACCESS_KEY", "localaccesskey"),
        aws_secret_access_key=os.environ.get("S3_SECRET_KEY", "localsecretkey"),
        region_name="us-east-1",
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )
