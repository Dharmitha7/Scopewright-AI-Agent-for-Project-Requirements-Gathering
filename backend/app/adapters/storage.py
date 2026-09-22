"""S3-compatible storage (MinIO locally, R2 in prod) with local-disk fallback."""

from __future__ import annotations

from pathlib import Path

from app.core.config import Settings


class LocalStorage:
    def __init__(self, root: Path) -> None:
        self._root = root
        self._root.mkdir(parents=True, exist_ok=True)

    def put(self, key: str, body: bytes, content_type: str) -> str:
        path = self._root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
        return key

    def get(self, key: str) -> bytes:
        return (self._root / key).read_bytes()


class S3Storage:
    def __init__(self, *, endpoint: str, bucket: str, access_key: str, secret_key: str) -> None:
        import boto3
        from botocore.client import Config

        self._bucket = bucket
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            config=Config(signature_version="s3v4"),
            region_name="us-east-1",
        )
        self._ensure_bucket()

    def _ensure_bucket(self) -> None:
        try:
            self._client.head_bucket(Bucket=self._bucket)
        except Exception:
            self._client.create_bucket(Bucket=self._bucket)

    def put(self, key: str, body: bytes, content_type: str) -> str:
        self._client.put_object(
            Bucket=self._bucket, Key=key, Body=body, ContentType=content_type
        )
        return key

    def get(self, key: str) -> bytes:
        obj = self._client.get_object(Bucket=self._bucket, Key=key)
        return obj["Body"].read()


def get_storage(settings: Settings):
    if settings.s3_endpoint and settings.s3_bucket:
        return S3Storage(
            endpoint=settings.s3_endpoint,
            bucket=settings.s3_bucket,
            access_key=settings.s3_access_key,
            secret_key=settings.s3_secret_key,
        )
    return LocalStorage(Path(settings.local_upload_dir))
