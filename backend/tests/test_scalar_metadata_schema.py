from backend.app.db.database import Base


def test_scalar_metadata_schema_is_encrypted_only() -> None:
    expected = {
        "users": ("email", "email_encrypted", "email_lookup_hash", False),
        "documents": ("filename", "filename_encrypted", None, False),
        "extractions": (
            "filename_display",
            "filename_display_encrypted",
            None,
            False,
        ),
        "clauses": ("title", "title_encrypted", None, True),
    }
    for table_name, (
        plaintext_name,
        encrypted_name,
        secondary_name,
        nullable,
    ) in expected.items():
        columns = Base.metadata.tables[table_name].c
        assert plaintext_name not in columns
        assert encrypted_name in columns
        assert columns[encrypted_name].nullable is nullable
        if secondary_name is not None:
            assert columns[secondary_name].nullable is False


def test_email_lookup_hash_is_unique_and_indexed() -> None:
    users = Base.metadata.tables["users"]
    assert users.c.email_lookup_hash.unique is True
    assert users.c.email_lookup_hash.index is True
