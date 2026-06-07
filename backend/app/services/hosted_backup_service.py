"""Encrypted off-platform logical backups for isolated hosted tenants."""
from __future__ import annotations

from base64 import urlsafe_b64decode
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import tempfile
from typing import Any, Callable, Optional

import boto3
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url


BACKUP_MAGIC = b"PHARMA_POS_BACKUP_V1\n"
BACKUP_TAG_SIZE = 16
CHUNK_SIZE = 1024 * 1024


@dataclass(frozen=True)
class HostedBackupConfig:
    database_url: str
    organization_uid: str
    encryption_key: str
    bucket: str
    endpoint_url: str
    region: str
    access_key_id: str
    secret_access_key: str
    daily_retention_days: int = 35
    monthly_retention_days: int = 366

    @classmethod
    def from_env(cls) -> "HostedBackupConfig":
        required = {
            "DATABASE_URL": os.getenv("DATABASE_URL"),
            "CLOUD_SYNC_ORGANIZATION_UID": os.getenv(
                "CLOUD_SYNC_ORGANIZATION_UID"
            ),
            "BACKUP_ENCRYPTION_KEY": os.getenv("BACKUP_ENCRYPTION_KEY"),
            "BACKUP_S3_BUCKET": os.getenv("BACKUP_S3_BUCKET"),
            "BACKUP_S3_ENDPOINT_URL": os.getenv("BACKUP_S3_ENDPOINT_URL"),
            "BACKUP_S3_REGION": os.getenv("BACKUP_S3_REGION"),
            "BACKUP_S3_ACCESS_KEY_ID": os.getenv("BACKUP_S3_ACCESS_KEY_ID"),
            "BACKUP_S3_SECRET_ACCESS_KEY": os.getenv(
                "BACKUP_S3_SECRET_ACCESS_KEY"
            ),
        }
        missing = [key for key, value in required.items() if not value]
        if missing:
            raise ValueError(
                "Hosted backup configuration is missing: "
                + ", ".join(sorted(missing))
            )
        return cls(
            database_url=required["DATABASE_URL"],
            organization_uid=required["CLOUD_SYNC_ORGANIZATION_UID"],
            encryption_key=required["BACKUP_ENCRYPTION_KEY"],
            bucket=required["BACKUP_S3_BUCKET"],
            endpoint_url=required["BACKUP_S3_ENDPOINT_URL"],
            region=required["BACKUP_S3_REGION"],
            access_key_id=required["BACKUP_S3_ACCESS_KEY_ID"],
            secret_access_key=required["BACKUP_S3_SECRET_ACCESS_KEY"],
            daily_retention_days=int(
                os.getenv("BACKUP_DAILY_RETENTION_DAYS", "35")
            ),
            monthly_retention_days=int(
                os.getenv("BACKUP_MONTHLY_RETENTION_DAYS", "366")
            ),
        )

    def encryption_key_bytes(self) -> bytes:
        try:
            key = urlsafe_b64decode(self.encryption_key.encode())
        except Exception as exc:
            raise ValueError("BACKUP_ENCRYPTION_KEY is not valid base64") from exc
        if len(key) != 32:
            raise ValueError("BACKUP_ENCRYPTION_KEY must decode to 32 bytes")
        return key


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def encrypt_backup(
    source: Path,
    destination: Path,
    *,
    encryption_key: bytes,
    header: dict[str, Any],
) -> dict[str, Any]:
    nonce = os.urandom(12)
    complete_header = {
        **header,
        "algorithm": "AES-256-GCM",
        "nonce": nonce.hex(),
        "plaintext_sha256": sha256_file(source),
    }
    header_bytes = json.dumps(
        complete_header,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    encryptor = Cipher(
        algorithms.AES(encryption_key),
        modes.GCM(nonce),
    ).encryptor()
    encryptor.authenticate_additional_data(header_bytes)

    with source.open("rb") as source_handle, destination.open("wb") as output:
        output.write(BACKUP_MAGIC)
        output.write(struct.pack(">I", len(header_bytes)))
        output.write(header_bytes)
        for chunk in iter(lambda: source_handle.read(CHUNK_SIZE), b""):
            output.write(encryptor.update(chunk))
        output.write(encryptor.finalize())
        output.write(encryptor.tag)

    return {
        **complete_header,
        "encrypted_sha256": sha256_file(destination),
        "encrypted_size_bytes": destination.stat().st_size,
    }


def decrypt_backup(
    source: Path,
    destination: Path,
    *,
    encryption_key: bytes,
) -> dict[str, Any]:
    with source.open("rb") as encrypted:
        if encrypted.read(len(BACKUP_MAGIC)) != BACKUP_MAGIC:
            raise ValueError("Unsupported hosted backup format")
        header_size = struct.unpack(">I", encrypted.read(4))[0]
        header_bytes = encrypted.read(header_size)
        header = json.loads(header_bytes)
        ciphertext_start = encrypted.tell()
        encrypted.seek(0, os.SEEK_END)
        ciphertext_end = encrypted.tell() - BACKUP_TAG_SIZE
        if ciphertext_end < ciphertext_start:
            raise ValueError("Hosted backup is truncated")
        encrypted.seek(ciphertext_end)
        tag = encrypted.read(BACKUP_TAG_SIZE)
        encrypted.seek(ciphertext_start)

        decryptor = Cipher(
            algorithms.AES(encryption_key),
            modes.GCM(bytes.fromhex(header["nonce"]), tag),
        ).decryptor()
        decryptor.authenticate_additional_data(header_bytes)
        remaining = ciphertext_end - ciphertext_start
        with destination.open("wb") as output:
            while remaining:
                chunk = encrypted.read(min(CHUNK_SIZE, remaining))
                if not chunk:
                    raise ValueError("Hosted backup ciphertext is truncated")
                output.write(decryptor.update(chunk))
                remaining -= len(chunk)
            output.write(decryptor.finalize())

    if sha256_file(destination) != header["plaintext_sha256"]:
        destination.unlink(missing_ok=True)
        raise ValueError("Decrypted backup checksum does not match manifest")
    return header


def database_revision(database_url: str) -> str:
    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            return str(
                connection.execute(
                    text("SELECT version_num FROM alembic_version")
                ).scalar_one()
            )
    finally:
        engine.dispose()


def _pg_dump_command(database_url: str, destination: Path) -> tuple[list[str], dict[str, str]]:
    url = make_url(database_url)
    if not url.host or not url.database or not url.username:
        raise ValueError("DATABASE_URL must include host, database, and username")
    command = [
        "pg_dump",
        "-h",
        url.host,
        "-p",
        str(url.port or 5432),
        "-U",
        url.username,
        "-d",
        url.database,
        "-F",
        "c",
        "-f",
        str(destination),
    ]
    environment = os.environ.copy()
    if url.password:
        environment["PGPASSWORD"] = url.password
    sslmode = url.query.get("sslmode")
    if sslmode:
        environment["PGSSLMODE"] = sslmode
    return command, environment


def build_s3_client(config: HostedBackupConfig):
    return boto3.client(
        "s3",
        endpoint_url=config.endpoint_url,
        region_name=config.region,
        aws_access_key_id=config.access_key_id,
        aws_secret_access_key=config.secret_access_key,
    )


def prune_prefix(
    s3_client,
    *,
    bucket: str,
    prefix: str,
    retention_days: int,
    now: datetime,
) -> int:
    cutoff = now - timedelta(days=retention_days)
    deleted = 0
    continuation_token: Optional[str] = None
    while True:
        request: dict[str, Any] = {"Bucket": bucket, "Prefix": prefix}
        if continuation_token:
            request["ContinuationToken"] = continuation_token
        response = s3_client.list_objects_v2(**request)
        stale = [
            {"Key": item["Key"]}
            for item in response.get("Contents", [])
            if item["LastModified"].astimezone(timezone.utc) < cutoff
        ]
        if stale:
            s3_client.delete_objects(
                Bucket=bucket,
                Delete={"Objects": stale, "Quiet": True},
            )
            deleted += len(stale)
        if not response.get("IsTruncated"):
            break
        continuation_token = response["NextContinuationToken"]
    return deleted


def create_hosted_backup(
    config: HostedBackupConfig,
    *,
    s3_client=None,
    now: Optional[datetime] = None,
    revision: Optional[str] = None,
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    revision = revision or database_revision(config.database_url)
    s3_client = s3_client or build_s3_client(config)
    timestamp = now.strftime("%Y%m%dT%H%M%SZ")
    backup_id = f"{timestamp}-{revision}"
    tenant_prefix = f"tenants/{config.organization_uid}"
    daily_key = f"{tenant_prefix}/daily/{now:%Y/%m}/{backup_id}.dump.enc"

    with tempfile.TemporaryDirectory(prefix="pharma-hosted-backup-") as temp_dir:
        temp_path = Path(temp_dir)
        dump_path = temp_path / f"{backup_id}.dump"
        encrypted_path = temp_path / f"{backup_id}.dump.enc"
        command, environment = _pg_dump_command(config.database_url, dump_path)
        runner(
            command,
            env=environment,
            check=True,
            capture_output=True,
            text=True,
        )
        if not dump_path.exists() or dump_path.stat().st_size == 0:
            raise RuntimeError("pg_dump completed without creating a backup file")

        manifest = encrypt_backup(
            dump_path,
            encrypted_path,
            encryption_key=config.encryption_key_bytes(),
            header={
                "backup_id": backup_id,
                "organization_uid": config.organization_uid,
                "schema_revision": revision,
                "created_at": now.isoformat(),
                "database_name": make_url(config.database_url).database,
                "format": "postgresql-custom",
            },
        )
        manifest["object_key"] = daily_key
        s3_client.upload_file(
            str(encrypted_path),
            config.bucket,
            daily_key,
            ExtraArgs={
                "ContentType": "application/octet-stream",
                "Metadata": {
                    "backup-id": backup_id,
                    "organization-uid": config.organization_uid,
                    "schema-revision": revision,
                    "encrypted-sha256": manifest["encrypted_sha256"],
                },
            },
        )
        s3_client.put_object(
            Bucket=config.bucket,
            Key=f"{daily_key}.json",
            Body=json.dumps(manifest, sort_keys=True).encode(),
            ContentType="application/json",
        )

        monthly_key = None
        if now.day == 1:
            monthly_key = (
                f"{tenant_prefix}/monthly/{now:%Y/%m}/{backup_id}.dump.enc"
            )
            s3_client.upload_file(
                str(encrypted_path),
                config.bucket,
                monthly_key,
                ExtraArgs={"ContentType": "application/octet-stream"},
            )
            monthly_manifest = {**manifest, "object_key": monthly_key}
            s3_client.put_object(
                Bucket=config.bucket,
                Key=f"{monthly_key}.json",
                Body=json.dumps(monthly_manifest, sort_keys=True).encode(),
                ContentType="application/json",
            )

    deleted_daily = prune_prefix(
        s3_client,
        bucket=config.bucket,
        prefix=f"{tenant_prefix}/daily/",
        retention_days=config.daily_retention_days,
        now=now,
    )
    deleted_monthly = prune_prefix(
        s3_client,
        bucket=config.bucket,
        prefix=f"{tenant_prefix}/monthly/",
        retention_days=config.monthly_retention_days,
        now=now,
    )
    return {
        **manifest,
        "monthly_object_key": monthly_key,
        "deleted_daily_objects": deleted_daily,
        "deleted_monthly_objects": deleted_monthly,
    }
