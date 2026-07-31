from __future__ import annotations

import base64
from dataclasses import dataclass
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.app.core.backup_contract import validate_artifact_path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
MYSQL_IMAGE = "mysql:8.4"


class RehearsalError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__("Synthetic backup/restore rehearsal failed.")
        self.code = code


@dataclass(frozen=True)
class RehearsalNames:
    suffix: str
    network: str
    source_container: str
    restore_container: str
    source_volume: str
    restore_volume: str
    app_image: str


def _names() -> RehearsalNames:
    suffix = uuid4().hex[:12]
    prefix = f"cc-rehearsal-{suffix}"
    return RehearsalNames(
        suffix=suffix,
        network=f"{prefix}-network",
        source_container=f"{prefix}-source",
        restore_container=f"{prefix}-restore",
        source_volume=f"{prefix}-source-data",
        restore_volume=f"{prefix}-restore-data",
        app_image=f"contract-check-rehearsal:{suffix}",
    )


def _synthetic_key(start: int) -> str:
    return base64.b64encode(
        bytes((start + offset) % 256 for offset in range(32))
    ).decode("ascii")


class MySQLRehearsal:
    def __init__(self) -> None:
        self.names = _names()
        self._temporary = tempfile.TemporaryDirectory(
            prefix="contract-check-backup-rehearsal-"
        )
        self.temporary_root = Path(self._temporary.name)
        self.artifact = self.temporary_root / "synthetic-backup.sql"
        password_seed = uuid4().hex
        self.database_name = "synthetic_contract_check"
        self.database_user = "synthetic_app"
        self.database_password = f"synthetic-app-{password_seed}"
        self.root_password = f"synthetic-root-{uuid4().hex}"
        self.keyring = json.dumps(
            [
                {
                    "key_id": "synthetic-backup-key",
                    "key": _synthetic_key(17),
                    "status": "active",
                }
            ],
            separators=(",", ":"),
        )
        self.email_key = _synthetic_key(81)
        self.created_containers: list[str] = []
        self.created_volumes: list[str] = []
        self.network_created = False
        self.image_created = False

    def _run(
        self,
        command: list[str],
        *,
        input_bytes: bytes | None = None,
        code: str,
    ) -> subprocess.CompletedProcess[bytes]:
        try:
            return subprocess.run(
                command,
                cwd=REPOSITORY_ROOT,
                input=input_bytes,
                capture_output=True,
                check=True,
            )
        except Exception:
            raise RehearsalError(code) from None

    def _write_env(self, name: str, values: dict[str, str]) -> Path:
        path = self.temporary_root / name
        path.write_text(
            "".join(f"{key}={value}\n" for key, value in values.items()),
            encoding="utf-8",
        )
        return path

    def setup(self) -> None:
        self._run(
            ["docker", "network", "create", self.names.network],
            code="NETWORK_CREATE_FAILED",
        )
        self.network_created = True
        for volume in (self.names.source_volume, self.names.restore_volume):
            self._run(["docker", "volume", "create", volume], code="VOLUME_CREATE_FAILED")
            self.created_volumes.append(volume)
        self._run(
            ["docker", "build", "-t", self.names.app_image, "."],
            code="APP_IMAGE_BUILD_FAILED",
        )
        self.image_created = True

    def _database_env_file(self, name: str) -> Path:
        return self._write_env(
            name,
            {
                "MYSQL_DATABASE": self.database_name,
                "MYSQL_USER": self.database_user,
                "MYSQL_PASSWORD": self.database_password,
                "MYSQL_ROOT_PASSWORD": self.root_password,
            },
        )

    def _app_env_file(self, name: str, database_host: str) -> Path:
        return self._write_env(
            name,
            {
                "DATABASE_URL": (
                    f"mysql+pymysql://{self.database_user}:{self.database_password}"
                    f"@{database_host}:3306/{self.database_name}"
                ),
                "DATA_ENCRYPTION_KEYS_JSON": self.keyring,
                "DATA_ENCRYPTION_ACTIVE_KEY_ID": "synthetic-backup-key",
                "EMAIL_LOOKUP_HMAC_KEY": self.email_key,
            },
        )

    def start_database(self, *, restore: bool) -> None:
        container = (
            self.names.restore_container if restore else self.names.source_container
        )
        volume = self.names.restore_volume if restore else self.names.source_volume
        alias = "restore-db" if restore else "source-db"
        env_file = self._database_env_file(f"{alias}.env")
        self._run(
            [
                "docker",
                "run",
                "-d",
                "--name",
                container,
                "--network",
                self.names.network,
                "--network-alias",
                alias,
                "--env-file",
                str(env_file),
                "-v",
                f"{volume}:/var/lib/mysql",
                MYSQL_IMAGE,
            ],
            code="DATABASE_START_FAILED",
        )
        self.created_containers.append(container)
        self._wait_for_database(container)

    def _wait_for_database(self, container: str) -> None:
        command = [
            "docker",
            "exec",
            container,
            "sh",
            "-c",
            'MYSQL_PWD="$MYSQL_PASSWORD" mysqladmin ping -h 127.0.0.1 -u "$MYSQL_USER" --silent',
        ]
        for _ in range(60):
            completed = subprocess.run(command, capture_output=True, check=False)
            if completed.returncode == 0:
                return
            time.sleep(1)
        raise RehearsalError("DATABASE_HEALTH_TIMEOUT")

    def migrate_source(self) -> None:
        env_file = self._app_env_file("source-app.env", "source-db")
        self._run(
            [
                "docker",
                "run",
                "--rm",
                "--network",
                self.names.network,
                "--env-file",
                str(env_file),
                self.names.app_image,
                "bash",
                "-lc",
                "cd backend && alembic upgrade head",
            ],
            code="MIGRATION_FAILED",
        )

    def seed_source(self) -> None:
        env_file = self._app_env_file("source-seed.env", "source-db")
        code = """
import os
from sqlalchemy import create_engine, text
from backend.app.core.email_lookup import build_email_lookup_hash
from backend.app.core.encryption_config import get_encryption_keyring
from backend.app.services.scalar_metadata_encryption import encrypt_document_filename, encrypt_user_email
user_id = "00000000-0000-4000-8000-000000000101"
document_id = "00000000-0000-4000-8000-000000000102"
keyring = get_encryption_keyring()
email = "synthetic-backup-user@example.invalid"
email_encrypted = encrypt_user_email(email, user_id=user_id, keyring=keyring)
filename_encrypted = encrypt_document_filename("synthetic-contract.txt", record_id=document_id, owner_id=user_id, keyring=keyring)
engine = create_engine(os.environ["DATABASE_URL"])
with engine.begin() as connection:
    connection.execute(text("INSERT INTO users (id,email_encrypted,email_lookup_hash,password_hash,is_active,auth_version,created_at,updated_at) VALUES (:id,:email,:lookup,:password,1,1,NOW(),NOW())"), {"id": user_id, "email": email_encrypted, "lookup": build_email_lookup_hash(email), "password": "synthetic-password-hash"})
    connection.execute(text("INSERT INTO documents (id,filename_encrypted,content_type,size_bytes,character_count,status,unclassified_sections,document_warnings,owner_id,created_at) VALUES (:id,:filename,'text/plain',23,23,'uploaded','[]','[]',:owner,NOW())"), {"id": document_id, "filename": filename_encrypted, "owner": user_id})
engine.dispose()
"""
        self._run(
            [
                "docker",
                "run",
                "--rm",
                "--network",
                self.names.network,
                "--env-file",
                str(env_file),
                self.names.app_image,
                "python",
                "-c",
                code,
            ],
            code="SYNTHETIC_SEED_FAILED",
        )

    def create_backup(self) -> None:
        validate_artifact_path(
            repository=REPOSITORY_ROOT,
            temporary_root=self.temporary_root,
            artifact=self.artifact,
            require_file=False,
        )
        completed = self._run(
            [
                "docker",
                "exec",
                self.names.source_container,
                "sh",
                "-c",
                'MYSQL_PWD="$MYSQL_PASSWORD" mysqldump --no-tablespaces --single-transaction --routines --events --triggers -u "$MYSQL_USER" "$MYSQL_DATABASE"',
            ],
            code="BACKUP_COMMAND_FAILED",
        )
        self.artifact.write_bytes(completed.stdout)
        validate_artifact_path(
            repository=REPOSITORY_ROOT,
            temporary_root=self.temporary_root,
            artifact=self.artifact,
            require_file=True,
        )
        artifact_bytes = self.artifact.read_bytes()
        for plaintext_marker in (
            b"synthetic-backup-user@example.invalid",
            b"synthetic-contract.txt",
        ):
            if plaintext_marker in artifact_bytes:
                raise RehearsalError("PLAINTEXT_IN_BACKUP")

    def restore_backup(self) -> None:
        validate_artifact_path(
            repository=REPOSITORY_ROOT,
            temporary_root=self.temporary_root,
            artifact=self.artifact,
            require_file=True,
        )
        with self.artifact.open("rb") as backup_stream:
            try:
                subprocess.run(
                    [
                        "docker",
                        "exec",
                        "-i",
                        self.names.restore_container,
                        "sh",
                        "-c",
                        'MYSQL_PWD="$MYSQL_PASSWORD" mysql -u "$MYSQL_USER" "$MYSQL_DATABASE"',
                    ],
                    cwd=REPOSITORY_ROOT,
                    stdin=backup_stream,
                    capture_output=True,
                    check=True,
                )
            except Exception:
                raise RehearsalError("RESTORE_COMMAND_FAILED") from None

    def verify_restore(self) -> None:
        env_file = self._app_env_file("restore-app.env", "restore-db")
        code = """
import os
from sqlalchemy import create_engine, inspect, text
from backend.app.db.database import Base
from backend.app.db import models as _models
from backend.app.services.readiness import get_readiness_status
from backend.app.core.encryption_config import get_encryption_keyring
from backend.app.services.scalar_metadata_encryption import decrypt_document_filename, decrypt_user_email, encrypt_user_email
user_id = "00000000-0000-4000-8000-000000000101"
document_id = "00000000-0000-4000-8000-000000000102"
database_url = os.environ["DATABASE_URL"]
assert get_readiness_status(database_url) == {"status": "ready"}
engine = create_engine(database_url)
inspector = inspect(engine)
tables = set(inspector.get_table_names())
assert set(Base.metadata.tables) <= tables
assert tables - set(Base.metadata.tables) == {"alembic_version"}
assert any(index.get("unique") for index in inspector.get_indexes("users") if index["name"] == "ix_users_email_lookup_hash")
assert any(fk["referred_table"] == "users" for fk in inspector.get_foreign_keys("documents"))
with engine.begin() as connection:
    row = connection.execute(text("SELECT u.email_encrypted,d.filename_encrypted,d.owner_id FROM users u JOIN documents d ON d.owner_id=u.id WHERE u.id=:user_id AND d.id=:document_id"), {"user_id": user_id, "document_id": document_id}).mappings().one()
    keyring = get_encryption_keyring()
    assert decrypt_user_email(row["email_encrypted"], user_id=user_id, keyring=keyring) == "synthetic-backup-user@example.invalid"
    assert decrypt_document_filename(row["filename_encrypted"], record_id=document_id, owner_id=user_id, keyring=keyring) == "synthetic-contract.txt"
    assert row["owner_id"] == user_id
    new_user = "00000000-0000-4000-8000-000000000103"
    encrypted = encrypt_user_email("synthetic-new-write@example.invalid", user_id=new_user, keyring=keyring)
    connection.execute(text("INSERT INTO users (id,email_encrypted,email_lookup_hash,password_hash,is_active,auth_version,created_at,updated_at) VALUES (:id,:email,:lookup,:password,1,1,NOW(),NOW())"), {"id": new_user, "email": encrypted, "lookup": "a" * 64, "password": "synthetic-password-hash"})
    assert connection.execute(text("SELECT COUNT(*) FROM users")).scalar_one() == 2
engine.dispose()
"""
        self._run(
            [
                "docker",
                "run",
                "--rm",
                "--network",
                self.names.network,
                "--env-file",
                str(env_file),
                self.names.app_image,
                "python",
                "-c",
                code,
            ],
            code="RESTORE_VERIFICATION_FAILED",
        )

    def cleanup(self) -> None:
        cleanup_failed = False
        for container in reversed(self.created_containers):
            completed = subprocess.run(
                ["docker", "rm", "-f", container],
                capture_output=True,
                check=False,
            )
            cleanup_failed = cleanup_failed or completed.returncode != 0
        for volume in reversed(self.created_volumes):
            completed = subprocess.run(
                ["docker", "volume", "rm", "-f", volume],
                capture_output=True,
                check=False,
            )
            cleanup_failed = cleanup_failed or completed.returncode != 0
        if self.network_created:
            completed = subprocess.run(
                ["docker", "network", "rm", self.names.network],
                capture_output=True,
                check=False,
            )
            cleanup_failed = cleanup_failed or completed.returncode != 0
        if self.image_created:
            completed = subprocess.run(
                ["docker", "image", "rm", self.names.app_image],
                capture_output=True,
                check=False,
            )
            cleanup_failed = cleanup_failed or completed.returncode != 0
        try:
            self._temporary.cleanup()
        except OSError:
            cleanup_failed = True
        if cleanup_failed:
            raise RehearsalError("CLEANUP_FAILED")


def _safe_result(stage: str, status: str, code: str) -> dict[str, str]:
    return {"stage": stage, "status": status, "safe_error_code": code}


def run_backup_rehearsal() -> tuple[dict[str, str], ...]:
    rehearsal = MySQLRehearsal()
    results: list[dict[str, str]] = []
    try:
        for stage, action in (
            ("isolated_environment", rehearsal.setup),
            ("source_database", lambda: rehearsal.start_database(restore=False)),
            ("alembic_upgrade", rehearsal.migrate_source),
            ("synthetic_seed", rehearsal.seed_source),
            ("backup_artifact", rehearsal.create_backup),
        ):
            try:
                action()
            except RehearsalError as exc:
                results.append(_safe_result(stage, "FAIL", exc.code))
                break
            results.append(_safe_result(stage, "PASS", "NONE"))
    finally:
        try:
            rehearsal.cleanup()
        except RehearsalError as exc:
            results.append(_safe_result("cleanup", "FAIL", exc.code))
        else:
            results.append(_safe_result("cleanup", "PASS", "NONE"))
    return tuple(results)


def main() -> int:
    results = run_backup_rehearsal()
    print(json.dumps({"results": results}, separators=(",", ":"), sort_keys=True))
    return 0 if all(item["status"] == "PASS" for item in results) else 1


if __name__ == "__main__":
    sys.exit(main())
