"""Migration 010 (audit events) on SQLite: up, down, up; and model parity."""

from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy.exc import IntegrityError

from cti.models.audit import AuditEvent

MIGRATION = Path(__file__).resolve().parents[1] / "alembic" / "versions" / "010_add_audit_events.py"
COLUMNS = {
    "id",
    "occurred_at",
    "actor_type",
    "actor_id",
    "actor_label",
    "action",
    "resource_type",
    "resource_id",
    "resource_label",
    "outcome",
    "summary",
}
INDEXES = {
    "ix_audit_events_occurred_at": ["occurred_at"],
    "ix_audit_events_actor": ["actor_type", "actor_id"],
    "ix_audit_events_action": ["action"],
    "ix_audit_events_resource": ["resource_type", "resource_id"],
    "ix_audit_events_outcome": ["outcome"],
}


def load_migration():  # type: ignore[no-untyped-def]
    spec = importlib.util.spec_from_file_location("cti_test_migration_010", MIGRATION)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run(migration, connection: sa.Connection, direction: str) -> None:  # type: ignore[no-untyped-def]
    with Operations.context(MigrationContext.configure(connection)):
        getattr(migration, direction)()


def _insert(connection: sa.Connection, **overrides: object) -> str:
    row: dict[str, object] = {
        "id": uuid.uuid4().hex,
        "occurred_at": "2026-11-02 10:00:00",
        "actor_type": "user",
        "action": "report.update",
        "resource_type": "report",
        "outcome": "succeeded",
    }
    row.update(overrides)
    columns = ", ".join(row)
    params = ", ".join(f":{name}" for name in row)
    connection.execute(sa.text(f"INSERT INTO audit_events ({columns}) VALUES ({params})"), row)
    return str(row["id"])


def _fails(connection: sa.Connection, **overrides: object) -> None:
    with pytest.raises(IntegrityError), connection.begin_nested():
        _insert(connection, **overrides)


def test_migration_010_up_down_up_on_sqlite() -> None:
    migration = load_migration()
    assert migration.revision == "010"
    assert migration.down_revision == "009"

    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys = ON")
        connection.exec_driver_sql("CREATE TABLE users (id CHAR(32) PRIMARY KEY)")

        _run(migration, connection, "upgrade")

        inspector = sa.inspect(connection)
        assert {c["name"] for c in inspector.get_columns("audit_events")} == COLUMNS
        assert inspector.get_foreign_keys("audit_events") == []
        indexes = {i["name"]: i["column_names"] for i in inspector.get_indexes("audit_events")}
        assert indexes == INDEXES
        nullable = {c["name"]: c["nullable"] for c in inspector.get_columns("audit_events")}
        assert {name for name, ok in nullable.items() if ok} == {
            "actor_id",
            "actor_label",
            "resource_id",
            "resource_label",
        }

        # The summary defaults to an empty JSON object.
        event_id = _insert(connection)
        summary = connection.execute(
            sa.text("SELECT summary FROM audit_events WHERE id = :id"), {"id": event_id}
        ).scalar()
        assert summary == "{}"

        for actor_type in ("user", "api_key", "system"):
            _insert(connection, actor_type=actor_type)
        for outcome in ("failed", "denied", "initiated", "completed", "interrupted"):
            _insert(connection, outcome=outcome)
        _fails(connection, actor_type="robot")
        _fails(connection, outcome="ok")
        _fails(connection, action=None)
        _fails(connection, occurred_at=None)

        # No foreign keys: an actor id that names no user is accepted.
        _insert(connection, actor_id=uuid.uuid4().hex)

        _run(migration, connection, "downgrade")
        assert "audit_events" not in sa.inspect(connection).get_table_names()
        assert "users" in sa.inspect(connection).get_table_names()

        _run(migration, connection, "upgrade")
        assert connection.exec_driver_sql("SELECT count(*) FROM audit_events").scalar() == 0


def test_model_matches_migration() -> None:
    """The ORM table used by the app (and test create_all) mirrors revision 010."""
    table = AuditEvent.__table__
    assert set(table.columns.keys()) == COLUMNS
    assert {i.name: [c.name for c in i.columns] for i in table.indexes} == INDEXES
    assert not table.foreign_keys
    checks = {c.name for c in table.constraints if isinstance(c, sa.CheckConstraint)}
    assert checks == {"ck_audit_events_actor_type", "ck_audit_events_outcome"}
    lengths = {
        name: table.columns[name].type.length
        for name in (
            "actor_type",
            "actor_id",
            "actor_label",
            "action",
            "resource_type",
            "resource_id",
            "resource_label",
            "outcome",
        )
    }
    assert lengths == {
        "actor_type": 16,
        "actor_id": 64,
        "actor_label": 255,
        "action": 64,
        "resource_type": 32,
        "resource_id": 64,
        "resource_label": 255,
        "outcome": 16,
    }
