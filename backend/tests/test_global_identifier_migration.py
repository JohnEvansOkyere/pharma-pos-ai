from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace


def _load_migration():
    migration_path = (
        Path(__file__).resolve().parents[1]
        / "alembic"
        / "versions"
        / "q2r3s4t5u6v7_add_global_sync_identifiers.py"
    )
    spec = importlib.util.spec_from_file_location(
        "global_identifier_migration",
        migration_path,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class RecordingBind:
    dialect = SimpleNamespace(name="postgresql")

    def __init__(self):
        self.statements = []

    def execute(self, statement, parameters=None):
        self.statements.append((statement, parameters))


def test_postgresql_global_identifier_backfill_is_set_based():
    migration = _load_migration()
    bind = RecordingBind()

    migration._backfill_postgresql(bind)

    sql = "\n".join(str(statement) for statement, _parameters in bind.statements)
    assert len(bind.statements) == 5
    assert 'CREATE EXTENSION IF NOT EXISTS "uuid-ossp"' in sql
    assert "UPDATE organizations" in sql
    assert "UPDATE branches" in sql
    assert "UPDATE devices" in sql
    assert "UPDATE ingested_sync_events AS event" in sql
    assert "FROM devices AS device" in sql
    assert "SELECT " not in sql.upper()
    assert all(
        set(statement._bindparams) <= {"namespace"}
        for statement, _parameters in bind.statements
    )
