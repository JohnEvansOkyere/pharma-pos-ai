from __future__ import annotations

from base64 import urlsafe_b64encode
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

from app.services.hosted_backup_service import (
    HostedBackupConfig,
    create_hosted_backup,
    decrypt_backup,
    encrypt_backup,
    prune_prefix,
)


class _FakeS3:
    def __init__(self, contents=None):
        self.uploads = []
        self.objects = {}
        self.contents = contents or []
        self.deleted = []

    def upload_file(self, filename, bucket, key, ExtraArgs=None):
        self.uploads.append(
            {
                "filename": filename,
                "bucket": bucket,
                "key": key,
                "extra": ExtraArgs,
                "body": Path(filename).read_bytes(),
            }
        )

    def put_object(self, **kwargs):
        self.objects[kwargs["Key"]] = kwargs

    def list_objects_v2(self, **kwargs):
        prefix = kwargs["Prefix"]
        return {
            "Contents": [
                item
                for item in self.contents
                if item["Key"].startswith(prefix)
            ],
            "IsTruncated": False,
        }

    def delete_objects(self, **kwargs):
        self.deleted.extend(kwargs["Delete"]["Objects"])


def _config() -> HostedBackupConfig:
    return HostedBackupConfig(
        database_url=(
            "postgresql://tenant_user:database-secret@db.internal:5432/"
            "tenant_db?sslmode=require"
        ),
        organization_uid="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        encryption_key=urlsafe_b64encode(b"k" * 32).decode(),
        bucket="tenant-backups",
        endpoint_url="https://objects.example",
        region="auto",
        access_key_id="tenant-access",
        secret_access_key="tenant-secret",
    )


def test_backup_encryption_round_trip_detects_plaintext_checksum(tmp_path):
    source = tmp_path / "source.dump"
    encrypted = tmp_path / "source.dump.enc"
    restored = tmp_path / "restored.dump"
    source.write_bytes((b"pharmacy-backup-data-" * 1000) + b"done")

    manifest = encrypt_backup(
        source,
        encrypted,
        encryption_key=b"k" * 32,
        header={
            "backup_id": "backup-1",
            "organization_uid": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        },
    )
    header = decrypt_backup(
        encrypted,
        restored,
        encryption_key=b"k" * 32,
    )

    assert restored.read_bytes() == source.read_bytes()
    assert header["plaintext_sha256"] == manifest["plaintext_sha256"]
    assert manifest["encrypted_sha256"]


def test_create_hosted_backup_uploads_daily_monthly_and_manifest():
    config = _config()
    fake_s3 = _FakeS3()
    captured = {}

    def runner(command, **kwargs):
        captured["command"] = command
        captured["env"] = kwargs["env"]
        destination = Path(command[command.index("-f") + 1])
        destination.write_bytes(b"custom-postgres-dump")

    result = create_hosted_backup(
        config,
        s3_client=fake_s3,
        now=datetime(2026, 6, 1, 2, 0, tzinfo=timezone.utc),
        revision="q2r3s4t5u6v7",
        runner=runner,
    )

    assert "database-secret" not in " ".join(captured["command"])
    assert captured["env"]["PGPASSWORD"] == "database-secret"
    assert captured["env"]["PGSSLMODE"] == "require"
    assert len(fake_s3.uploads) == 2
    assert "/daily/2026/06/" in result["object_key"]
    assert "/monthly/2026/06/" in result["monthly_object_key"]
    assert f'{result["object_key"]}.json' in fake_s3.objects
    manifest = json.loads(
        fake_s3.objects[f'{result["object_key"]}.json']["Body"]
    )
    assert manifest["schema_revision"] == "q2r3s4t5u6v7"
    assert manifest["organization_uid"] == config.organization_uid
    assert manifest["encrypted_sha256"]


def test_prune_prefix_deletes_only_objects_older_than_retention():
    now = datetime(2026, 6, 7, tzinfo=timezone.utc)
    fake_s3 = _FakeS3(
        [
            {
                "Key": "tenants/t1/daily/old.dump.enc",
                "LastModified": now - timedelta(days=36),
            },
            {
                "Key": "tenants/t1/daily/recent.dump.enc",
                "LastModified": now - timedelta(days=10),
            },
            {
                "Key": "tenants/t2/daily/other.dump.enc",
                "LastModified": now - timedelta(days=100),
            },
        ]
    )

    deleted = prune_prefix(
        fake_s3,
        bucket="tenant-backups",
        prefix="tenants/t1/daily/",
        retention_days=35,
        now=now,
    )

    assert deleted == 1
    assert fake_s3.deleted == [{"Key": "tenants/t1/daily/old.dump.enc"}]
