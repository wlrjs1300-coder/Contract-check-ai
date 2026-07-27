from backend.app.core.email_lookup import build_email_lookup_hash
from backend.app.core.encryption_config import get_encryption_keyring
from backend.app.db.models import Clause, Document, Extraction, User
from backend.app.services.scalar_metadata_encryption import (
    encrypt_clause_title,
    encrypt_document_filename,
    encrypt_extraction_filename_display,
    encrypt_user_email,
)


TEST_USER_ID = "00000000-0000-4000-8000-000000000001"


def encrypted_user(**values):
    email = values.pop("email")
    user_id = values["id"]
    values["email_encrypted"] = encrypt_user_email(
        email, user_id=user_id, keyring=get_encryption_keyring()
    )
    values["email_lookup_hash"] = build_email_lookup_hash(email)
    return User(**values)


def encrypted_document(**values):
    filename = values.pop("filename")
    values["filename_encrypted"] = encrypt_document_filename(
        filename,
        record_id=values["id"],
        owner_id=values["owner_id"],
        keyring=get_encryption_keyring(),
    )
    return Document(**values)


def encrypted_extraction(**values):
    filename = values.pop("filename_display")
    values["filename_display_encrypted"] = encrypt_extraction_filename_display(
        filename,
        record_id=values["id"],
        owner_id=values["owner_id"],
        keyring=get_encryption_keyring(),
    )
    return Extraction(**values)


def encrypted_clause(*, owner_id: str = TEST_USER_ID, **values):
    if "id" not in values:
        return Clause(**values)
    title = values.pop("title", None)
    values["title_encrypted"] = encrypt_clause_title(
        title,
        clause_id=values["id"],
        owner_id=owner_id,
        keyring=get_encryption_keyring(),
    )
    return Clause(**values)
