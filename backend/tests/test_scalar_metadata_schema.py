from backend.app.db.database import Base


def test_scalar_metadata_columns_are_nullable_and_additive() -> None:
    expected = {
        "users": ("email", "email_encrypted", "email_lookup_hash"),
        "documents": ("filename", "filename_encrypted"),
        "extractions": ("filename_display", "filename_display_encrypted"),
        "clauses": ("title", "title_encrypted"),
    }
    for table_name, column_names in expected.items():
        columns = Base.metadata.tables[table_name].c
        assert set(column_names).issubset(columns.keys())
        for encrypted_name in column_names[1:]:
            assert columns[encrypted_name].nullable is True


def test_email_lookup_hash_has_no_additive_index_or_unique_constraint() -> None:
    users = Base.metadata.tables["users"]
    assert users.c.email.unique is True
    assert users.c.email.index is True
    assert users.c.email_lookup_hash.unique is None
    assert users.c.email_lookup_hash.index is None
