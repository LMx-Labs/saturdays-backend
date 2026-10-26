"""Keep migration verification expectations aligned with application tables."""

import app.models  # noqa: F401
from app.core.database import Base
from scripts.verify_migrations import FINAL_SCHEMA_COLUMNS


def test_final_schema_expectations_match_declared_tables():
    for table_name, expected_columns in FINAL_SCHEMA_COLUMNS.items():
        assert table_name in Base.metadata.tables
        actual_columns = set(Base.metadata.tables[table_name].columns.keys())
        assert expected_columns <= actual_columns

    assert "id" not in Base.metadata.tables["system_feature_flags"].columns
