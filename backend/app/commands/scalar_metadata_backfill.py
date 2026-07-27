from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.auth import normalize_email
from backend.app.core.email_lookup import build_email_lookup_hash
from backend.app.core.encryption_config import get_encryption_keyring
from backend.app.db.database import SessionLocal
from backend.app.db.models import Clause, Document, Extraction, User
from backend.app.services.scalar_encryption import ScalarDecryptionError
from backend.app.services.scalar_metadata_encryption import (
    decrypt_clause_title,
    decrypt_document_filename,
    decrypt_extraction_filename_display,
    decrypt_user_email,
    encrypt_clause_title,
    encrypt_document_filename,
    encrypt_extraction_filename_display,
    encrypt_user_email,
)
from backend.app.services.scalar_metadata_transition import resolve_transition_scalar


@dataclass
class Counts:
    rows: int = 0
    plaintext_only: int = 0
    encrypted_only: int = 0
    matching_dual: int = 0
    missing: int = 0
    mismatched_dual: int = 0
    email_hash_missing: int = 0
    email_hash_mismatch: int = 0
    duplicate_normalized_email: int = 0
    updated: int = 0
    skipped: int = 0


def _state(
    plaintext,
    encrypted,
    decrypt_value,
    *,
    allow_missing: bool,
):
    decrypted = decrypt_value(encrypted) if encrypted is not None else None
    return resolve_transition_scalar(
        plaintext,
        decrypted,
        encrypted_present=encrypted is not None,
        allow_missing=allow_missing,
    )


def inventory(db: Session) -> dict[str, Counts]:
    keyring = get_encryption_keyring()
    result = {name: Counts() for name in ("users", "documents", "extractions", "clauses")}
    seen_emails: dict[str, int] = {}
    resources = (
        ("users", db.scalars(select(User).order_by(User.id)).all()),
        ("documents", db.scalars(select(Document).order_by(Document.id)).all()),
        ("extractions", db.scalars(select(Extraction).order_by(Extraction.id)).all()),
        (
            "clauses",
            db.scalars(select(Clause).order_by(Clause.id)).all(),
        ),
    )
    for name, rows in resources:
        counts = result[name]
        for row in rows:
            counts.rows += 1
            try:
                if name == "users":
                    resolved = _state(
                        row.email,
                        row.email_encrypted,
                        lambda value: decrypt_user_email(
                            value, user_id=row.id, keyring=keyring
                        ),
                        allow_missing=False,
                    )
                    normalized = normalize_email(resolved.value or "")
                    seen_emails[normalized] = seen_emails.get(normalized, 0) + 1
                    expected_hash = build_email_lookup_hash(normalized)
                    if row.email_lookup_hash is None:
                        counts.email_hash_missing += 1
                    elif row.email_lookup_hash != expected_hash:
                        counts.email_hash_mismatch += 1
                elif name == "documents":
                    resolved = _state(
                        row.filename,
                        row.filename_encrypted,
                        lambda value: decrypt_document_filename(
                            value,
                            record_id=row.id,
                            owner_id=row.owner_id,
                            keyring=keyring,
                        ),
                        allow_missing=False,
                    )
                elif name == "extractions":
                    resolved = _state(
                        row.filename_display,
                        row.filename_display_encrypted,
                        lambda value: decrypt_extraction_filename_display(
                            value,
                            record_id=row.id,
                            owner_id=row.owner_id,
                            keyring=keyring,
                        ),
                        allow_missing=False,
                    )
                else:
                    resolved = _state(
                        row.title,
                        row.title_encrypted,
                        lambda value: decrypt_clause_title(
                            value,
                            clause_id=row.id,
                            owner_id=row.document.owner_id,
                            keyring=keyring,
                        ),
                        allow_missing=True,
                    )
                count_field = (
                    "plaintext_only"
                    if resolved.state == "legacy_plaintext"
                    else resolved.state
                )
                setattr(counts, count_field, getattr(counts, count_field) + 1)
            except ScalarDecryptionError:
                counts.mismatched_dual += 1
    duplicates = sum(count - 1 for count in seen_emails.values() if count > 1)
    result["users"].duplicate_normalized_email = duplicates
    return result


def backfill(
    db: Session,
    *,
    batch_size: int = 200,
    after_id: str = "",
) -> dict[str, Counts]:
    if batch_size <= 0:
        raise ValueError("Invalid batch size.")
    report = inventory(db)
    if (
        report["users"].duplicate_normalized_email
        or any(item.mismatched_dual for item in report.values())
        or report["users"].email_hash_mismatch
    ):
        raise ScalarDecryptionError("Scalar metadata backfill validation failed.")
    keyring = get_encryption_keyring()
    for model, plaintext_name, encrypted_name, encrypt_value in (
        (
            User,
            "email",
            "email_encrypted",
            lambda row, value: encrypt_user_email(value, user_id=row.id, keyring=keyring),
        ),
        (
            Document,
            "filename",
            "filename_encrypted",
            lambda row, value: encrypt_document_filename(
                value, record_id=row.id, owner_id=row.owner_id, keyring=keyring
            ),
        ),
        (
            Extraction,
            "filename_display",
            "filename_display_encrypted",
            lambda row, value: encrypt_extraction_filename_display(
                value, record_id=row.id, owner_id=row.owner_id, keyring=keyring
            ),
        ),
        (
            Clause,
            "title",
            "title_encrypted",
            lambda row, value: encrypt_clause_title(
                value,
                clause_id=row.id,
                owner_id=row.document.owner_id,
                keyring=keyring,
            ),
        ),
    ):
        cursor = after_id
        while True:
            rows = db.scalars(
                select(model)
                .where(model.id > cursor)
                .order_by(model.id)
                .limit(batch_size)
            ).all()
            if not rows:
                break
            for row in rows:
                plaintext = getattr(row, plaintext_name)
                encrypted = getattr(row, encrypted_name)
                if encrypted is None and plaintext is not None:
                    setattr(row, encrypted_name, encrypt_value(row, plaintext))
                    if isinstance(row, User):
                        row.email_lookup_hash = build_email_lookup_hash(row.email)
                    report[model.__tablename__].updated += 1
                else:
                    report[model.__tablename__].skipped += 1
            db.commit()
            cursor = rows[-1].id
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("inventory", "backfill"))
    parser.add_argument("--batch-size", type=int, default=200)
    parser.add_argument("--after-id", default="")
    args = parser.parse_args()
    with SessionLocal() as db:
        report = (
            inventory(db)
            if args.action == "inventory"
            else backfill(db, batch_size=args.batch_size, after_id=args.after_id)
        )
    print(json.dumps({key: asdict(value) for key, value in report.items()}, sort_keys=True))


if __name__ == "__main__":
    main()
