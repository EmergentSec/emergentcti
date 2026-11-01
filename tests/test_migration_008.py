"""Migration 008 (analyst confidence floor and pinned override) on SQLite."""

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
    Path(__file__).resolve().parents[1] / "alembic" / "versions" / "008_add_analyst_confidence.py"
)
NEW_COLUMNS = {
    "manual_confidence",
    "confidence_override",
    "override_set_at",
    "override_set_by_id",
}


def load_migration():  # type: ignore[no-untyped-def]
    spec = importlib.util.spec_from_file_location("cti_test_migration_008", MIGRATION)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def create_pre_008_schema(connection: sa.Connection) -> None:
    connection.exec_driver_sql("CREATE TABLE users (id CHAR(32) PRIMARY KEY)")
    connection.exec_driver_sql(
        """
        CREATE TABLE observables (
            id CHAR(32) PRIMARY KEY,
            confidence_score INTEGER NOT NULL,
            value VARCHAR(2048) NOT NULL
        )
        """
    )
    connection.exec_driver_sql(
        """
        CREATE TABLE observable_sources (
            id CHAR(32) PRIMARY KEY,
            observable_id CHAR(32) NOT NULL,
            source_confidence INTEGER NOT NULL DEFAULT 50,
            FOREIGN KEY(observable_id) REFERENCES observables(id) ON DELETE CASCADE
        )
        """
    )
    connection.exec_driver_sql(
        """
        CREATE TABLE report_observables (
            report_id CHAR(32) NOT NULL,
            observable_id CHAR(32) NOT NULL,
            analyst_confidence INTEGER,
            PRIMARY KEY(report_id, observable_id),
            FOREIGN KEY(observable_id) REFERENCES observables(id) ON DELETE CASCADE
        )
        """
    )


def _run(migration, connection: sa.Connection, direction: str) -> None:  # type: ignore[no-untyped-def]
    with Operations.context(MigrationContext.configure(connection)):
        getattr(migration, direction)()


def test_migration_008_up_down_up_on_sqlite_with_backfill() -> None:
    migration = load_migration()
    assert migration.revision == "008"
    assert migration.down_revision == "007"

    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        create_pre_008_schema(connection)
        manual_id = uuid.uuid4().hex
        feed_id = uuid.uuid4().hex
        source_id = uuid.uuid4().hex
        user_id = uuid.uuid4().hex
        connection.exec_driver_sql(f"INSERT INTO users VALUES ('{user_id}')")
        raised_id = uuid.uuid4().hex
        raised_source_id = uuid.uuid4().hex
        report_id = uuid.uuid4().hex
        imported_id = uuid.uuid4().hex
        imported_then_raised_id = uuid.uuid4().hex
        connection.exec_driver_sql(
            "INSERT INTO observables VALUES "
            f"('{manual_id}', 73, 'manual.example'), ('{feed_id}', 55, 'feed.example'), "
            f"('{raised_id}', 85, 'raised.example'), "
            f"('{imported_id}', 60, 'report.example'), "
            f"('{imported_then_raised_id}', 80, 'report-raised.example')"
        )
        # feed.example is explained by its feed (55). raised.example was seen
        # by a feed at 40 and manually raised to 85, which nothing recorded.
        connection.exec_driver_sql(
            f"INSERT INTO observable_sources VALUES ('{source_id}', '{feed_id}', 55), "
            f"('{raised_source_id}', '{raised_id}', 40)"
        )
        connection.exec_driver_sql(
            "INSERT INTO report_observables VALUES "
            f"('{report_id}', '{imported_id}', 60), "
            f"('{report_id}', '{imported_then_raised_id}', 60)"
        )

        _run(migration, connection, "upgrade")
        inspector = sa.inspect(connection)
        columns = {item["name"] for item in inspector.get_columns("observables")}
        assert columns >= {"id", "confidence_score", "value"} | NEW_COLUMNS
        checks = {item["name"] for item in inspector.get_check_constraints("observables")}
        assert {
            "ck_observables_manual_confidence",
            "ck_observables_confidence_override",
            "ck_observables_override_set_at",
        } <= checks
        foreign_keys = {item["name"]: item for item in inspector.get_foreign_keys("observables")}
        setter_fk = foreign_keys["fk_observables_override_set_by_id"]
        assert setter_fk["referred_table"] == "users"
        assert setter_fk["options"].get("ondelete") == "SET NULL"

        rows = connection.exec_driver_sql(
            "SELECT value, manual_confidence FROM observables ORDER BY value"
        ).all()
        assert rows == [
            ("feed.example", None),
            ("manual.example", 73),
            ("raised.example", 85),  # unexplained confidence becomes the analyst floor
            ("report-raised.example", 80),
            ("report.example", None),
        ]
        for column in ("manual_confidence", "confidence_override"):
            with pytest.raises(IntegrityError), connection.begin_nested():
                connection.exec_driver_sql(
                    f"UPDATE observables SET {column} = 101 WHERE id = '{manual_id}'"
                )
        with pytest.raises(IntegrityError), connection.begin_nested():
            connection.exec_driver_sql(
                "UPDATE observables SET override_set_at = CURRENT_TIMESTAMP "
                f"WHERE id = '{manual_id}'"
            )

        connection.exec_driver_sql(
            "UPDATE observables SET confidence_override = 20, "
            f"override_set_at = CURRENT_TIMESTAMP, override_set_by_id = '{user_id}' "
            f"WHERE id = '{manual_id}'"
        )
        _run(migration, connection, "downgrade")
        remaining = {item["name"] for item in sa.inspect(connection).get_columns("observables")}
        assert remaining == {"id", "confidence_score", "value"}
        assert connection.exec_driver_sql("SELECT count(*) FROM observables").scalar() == 5

        _run(migration, connection, "upgrade")
        columns = {item["name"] for item in sa.inspect(connection).get_columns("observables")}
        assert columns >= NEW_COLUMNS
        assert (
            connection.exec_driver_sql(
                "SELECT manual_confidence FROM observables WHERE value = 'manual.example'"
            ).scalar()
            == 73
        )
