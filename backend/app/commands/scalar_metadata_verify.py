from __future__ import annotations

import json
from collections import Counter

from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from backend.app.core.email_lookup import (
    build_email_lookup_hash,
    compare_email_lookup_hash,
)
from backend.app.core.encryption_config import get_encryption_keyring
from backend.app.db.database import SessionLocal
from backend.app.db.models import Clause, Document, Extraction, User
from backend.app.services.scalar_metadata_encryption import (
    decrypt_clause_title,
    decrypt_document_filename,
    decrypt_extraction_filename_display,
    decrypt_user_email,
)


def verify(db: Session) -> dict[str, object]:
    keyring = get_encryption_keyring()
    bind = db.get_bind()
    columns = {
        table: {column["name"] for column in inspect(bind).get_columns(table)}
        for table in ("users", "documents", "extractions", "clauses")
    }
    plaintext_columns = {
        "users": "email",
        "documents": "filename",
        "extractions": "filename_display",
        "clauses": "title",
    }
    report: dict[str, object] = {
        "plaintext_column_count": sum(
            name in columns[table]
            for table, name in plaintext_columns.items()
        ),
        "rows": {},
        "decrypt_failures": 0,
        "email_hash_mismatches": 0,
        "duplicate_email_hashes": 0,
        "key_usage": {},
    }
    key_usage: Counter[str] = Counter()

    users = db.scalars(select(User).order_by(User.id)).all()
    hashes: Counter[str] = Counter()
    for user in users:
        try:
            email = decrypt_user_email(
                user.email_encrypted,
                user_id=user.id,
                keyring=keyring,
            )
            if not compare_email_lookup_hash(
                user.email_lookup_hash,
                build_email_lookup_hash(email),
            ):
                report["email_hash_mismatches"] += 1
            hashes[user.email_lookup_hash] += 1
            key_usage[json.loads(user.email_encrypted)["key_id"]] += 1
        except Exception:
            report["decrypt_failures"] += 1

    for document in db.scalars(select(Document).order_by(Document.id)):
        try:
            decrypt_document_filename(
                document.filename_encrypted,
                record_id=document.id,
                owner_id=document.owner_id,
                keyring=keyring,
            )
            key_usage[json.loads(document.filename_encrypted)["key_id"]] += 1
        except Exception:
            report["decrypt_failures"] += 1

    for extraction in db.scalars(select(Extraction).order_by(Extraction.id)):
        try:
            decrypt_extraction_filename_display(
                extraction.filename_display_encrypted,
                record_id=extraction.id,
                owner_id=extraction.owner_id,
                keyring=keyring,
            )
            key_usage[json.loads(extraction.filename_display_encrypted)["key_id"]] += 1
        except Exception:
            report["decrypt_failures"] += 1

    for clause in db.scalars(select(Clause).order_by(Clause.id)):
        if clause.title_encrypted is None:
            continue
        try:
            decrypt_clause_title(
                clause.title_encrypted,
                clause_id=clause.id,
                owner_id=clause.document.owner_id,
                keyring=keyring,
            )
            key_usage[json.loads(clause.title_encrypted)["key_id"]] += 1
        except Exception:
            report["decrypt_failures"] += 1

    report["rows"] = {
        "users": len(users),
        "documents": db.query(Document).count(),
        "extractions": db.query(Extraction).count(),
        "clauses": db.query(Clause).count(),
    }
    report["duplicate_email_hashes"] = sum(
        count - 1 for count in hashes.values() if count > 1
    )
    report["key_usage"] = dict(sorted(key_usage.items()))
    return report


def main() -> None:
    with SessionLocal() as db:
        report = verify(db)
    print(json.dumps(report, sort_keys=True))
    if (
        report["plaintext_column_count"]
        or report["decrypt_failures"]
        or report["email_hash_mismatches"]
        or report["duplicate_email_hashes"]
    ):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
