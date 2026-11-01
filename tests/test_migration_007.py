"""Migration 007 (report import attribution) on SQLite.

Earlier migrations use PostgreSQL-only defaults, so this builds the 005-era
``report_observables`` shape by hand and runs 007 against it. PostgreSQL is
covered by the opt-in suite in ``test_postgres_policies.py``.
"""

from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy.exc import IntegrityError

MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "007_add_report_import_attribution.py"
)
NEW_COLUMNS = {"imported_at", "imported_by_id", "analyst_confidence", "source_excerpt"}


def load_migration():  # type: ignore[no-untyped-def]
    spec = importlib.util.spec_from_file_location("cti_test_migration_007", MIGRATION)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def create_pre_007_schema(connection: sa.Connection) -> None:
    connection.exec_driver_sql("CREATE TABLE users (id CHAR(32) PRIMARY KEY)")
    connection.exec_driver_sql("CREATE TABLE reports (id CHAR(32) PRIMARY KEY)")
    connection.exec_driver_sql("CREATE TABLE observables (id CHAR(32) PRIMARY KEY)")
    connection.exec_driver_sql(
        """
        CREATE TABLE report_observables (
            report_id CHAR(32) NOT NULL,
            observable_id CHAR(32) NOT NULL,
            created_at DATETIME DEFAULT (CURRENT_TIMESTAMP) NOT NULL,
            PRIMARY KEY (report_id, observable_id),
            CONSTRAINT fk_report_observables_report_id FOREIGN KEY(report_id)
                REFERENCES reports (id) ON DELETE CASCADE,
            CONSTRAINT fk_report_observables_observable_id FOREIGN KEY(observable_id)
                REFERENCES observables (id) ON DELETE CASCADE
        )
        """
    )
    connection.exec_driver_sql(
        "CREATE INDEX ix_report_observables_observable_id ON report_observables (observable_id)"
    )


def test_migration_007_upgrade_and_downgrade_on_sqlite() -> None:
    migration = load_migration()
    assert migration.revision == "007"
    assert migration.down_revision == "006"

    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        create_pre_007_schema(connection)
        report_id, observable_id = uuid.uuid4().hex, uuid.uuid4().hex
        connection.exec_driver_sql(f"INSERT INTO reports VALUES ('{report_id}')")
        connection.exec_driver_sql(f"INSERT INTO observables VALUES ('{observable_id}')")
        connection.exec_driver_sql(
            "INSERT INTO report_observables (report_id, observable_id) "
            f"VALUES ('{report_id}', '{observable_id}')"
        )

        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()

        inspector = sa.inspect(connection)
        columns = {column["name"]: column for column in inspector.get_columns("report_observables")}
        assert set(columns) >= NEW_COLUMNS
        assert all(columns[name]["nullable"] for name in NEW_COLUMNS)
        assert columns["source_excerpt"]["type"].length == 500
        foreign_keys = {fk["name"]: fk for fk in inspector.get_foreign_keys("report_observables")}
        imported_by = foreign_keys["fk_report_observables_imported_by_id"]
        assert imported_by["referred_table"] == "users"
        assert imported_by["options"].get("ondelete") == "SET NULL"
        assert {"fk_report_observables_report_id", "fk_report_observables_observable_id"} <= set(
            foreign_keys
        )
        checks = {c["name"] for c in inspector.get_check_constraints("report_observables")}
        assert "ck_report_observables_analyst_confidence" in checks
        indexes = {index["name"] for index in inspector.get_indexes("report_observables")}
        assert "ix_report_observables_observable_id" in indexes

        # Existing manual links survive with null attribution.
        row = connection.exec_driver_sql(
            "SELECT imported_at, analyst_confidence FROM report_observables"
        ).one()
        assert tuple(row) == (None, None)

        for confidence in (0, 100):
            connection.exec_driver_sql(
                f"UPDATE report_observables SET analyst_confidence = {confidence}"
            )
        with pytest.raises(IntegrityError), connection.begin_nested():
            connection.exec_driver_sql("UPDATE report_observables SET analyst_confidence = 101")

        with Operations.context(MigrationContext.configure(connection)):
            migration.downgrade()

        inspector = sa.inspect(connection)
        remaining = {column["name"] for column in inspector.get_columns("report_observables")}
        assert remaining == {"report_id", "observable_id", "created_at"}
        assert connection.exec_driver_sql("SELECT count(*) FROM report_observables").scalar() == 1
