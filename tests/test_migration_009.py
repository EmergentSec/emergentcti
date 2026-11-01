"""Migration 009 (tags and TLP markings) on SQLite: up, down, up."""

from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy.exc import IntegrityError

MIGRATION = Path(__file__).resolve().parents[1] / "alembic" / "versions" / "009_add_tags_and_tlp.py"
OBSERVABLE_COLUMNS = {
    "manual_tlp",
    "tlp_override",
    "tlp_override_reason",
    "tlp_override_set_at",
    "tlp_override_set_by_id",
}
NEW_TABLES = {"tags", "observable_tags", "report_tags", "export_profile_tags"}


def load_migration():  # type: ignore[no-untyped-def]
    spec = importlib.util.spec_from_file_location("cti_test_migration_009", MIGRATION)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def create_pre_009_schema(connection: sa.Connection) -> None:
    connection.exec_driver_sql("CREATE TABLE users (id CHAR(32) PRIMARY KEY)")
    connection.exec_driver_sql(
        "CREATE TABLE feeds (id CHAR(32) PRIMARY KEY, name VARCHAR(256) NOT NULL)"
    )
    connection.exec_driver_sql(
        "CREATE TABLE reports (id CHAR(32) PRIMARY KEY, title VARCHAR(500) NOT NULL)"
    )
    connection.exec_driver_sql(
        "CREATE TABLE observables (id CHAR(32) PRIMARY KEY, value VARCHAR(2048) NOT NULL)"
    )
    connection.exec_driver_sql(
        "CREATE TABLE export_profiles (id CHAR(32) PRIMARY KEY, name VARCHAR(100) NOT NULL)"
    )


def _run(migration, connection: sa.Connection, direction: str) -> None:  # type: ignore[no-untyped-def]
    with Operations.context(MigrationContext.configure(connection)):
        getattr(migration, direction)()


def _columns(connection: sa.Connection, table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(connection).get_columns(table)}


def _fails(connection: sa.Connection, sql: str) -> None:
    with pytest.raises(IntegrityError), connection.begin_nested():
        connection.exec_driver_sql(sql)


def test_migration_009_up_down_up_on_sqlite() -> None:
    migration = load_migration()
    assert migration.revision == "009"
    assert migration.down_revision == "008"

    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys = ON")
        create_pre_009_schema(connection)
        ids = {name: uuid.uuid4().hex for name in ("feed", "report", "obs", "profile", "user")}
        connection.exec_driver_sql(f"INSERT INTO users VALUES ('{ids['user']}')")
        connection.exec_driver_sql(f"INSERT INTO feeds VALUES ('{ids['feed']}', 'F')")
        connection.exec_driver_sql(f"INSERT INTO reports VALUES ('{ids['report']}', 'R')")
        connection.exec_driver_sql(f"INSERT INTO observables VALUES ('{ids['obs']}', 'x')")
        connection.exec_driver_sql(f"INSERT INTO export_profiles VALUES ('{ids['profile']}', 'P')")

        _run(migration, connection, "upgrade")

        inspector = sa.inspect(connection)
        assert set(inspector.get_table_names()) >= NEW_TABLES
        assert "tlp" in _columns(connection, "feeds")
        assert "tlp" in _columns(connection, "reports")
        assert _columns(connection, "observables") >= OBSERVABLE_COLUMNS
        assert "destination" in _columns(connection, "export_profiles")
        # Nothing is backfilled; existing profiles become internal.
        assert connection.exec_driver_sql("SELECT tlp FROM feeds").scalar() is None
        assert connection.exec_driver_sql("SELECT tlp FROM reports").scalar() is None
        assert connection.exec_driver_sql(
            "SELECT manual_tlp, tlp_override FROM observables"
        ).one() == (None, None)
        assert (
            connection.exec_driver_sql("SELECT destination FROM export_profiles").scalar()
            == "internal"
        )
        fk = {f["name"]: f for f in inspector.get_foreign_keys("observables")}[
            "fk_observables_tlp_override_set_by_id"
        ]
        assert fk["referred_table"] == "users" and fk["options"].get("ondelete") == "SET NULL"
        profile_tag_fks = {
            f["referred_table"]: f["options"].get("ondelete")
            for f in inspector.get_foreign_keys("export_profile_tags")
        }
        assert profile_tag_fks == {"export_profiles": "CASCADE", "tags": "RESTRICT"}
        assert {"ix_observable_tags_tag_id"} <= {
            i["name"] for i in inspector.get_indexes("observable_tags")
        }

        # Every marking value is accepted; anything else is refused.
        for value in ("clear", "green", "amber", "amber+strict", "red"):
            connection.exec_driver_sql(f"UPDATE feeds SET tlp = '{value}'")
            connection.exec_driver_sql(f"UPDATE reports SET tlp = '{value}'")
            connection.exec_driver_sql(f"UPDATE observables SET manual_tlp = '{value}'")
        for table, column in (
            ("feeds", "tlp"),
            ("reports", "tlp"),
            ("observables", "manual_tlp"),
        ):
            _fails(connection, f"UPDATE {table} SET {column} = 'TLP:RED'")
            _fails(connection, f"UPDATE {table} SET {column} = 'white'")
        _fails(connection, "UPDATE export_profiles SET destination = 'external_ai'")
        # Override fields are all-or-nothing.
        _fails(connection, "UPDATE observables SET tlp_override = 'red'")
        _fails(connection, "UPDATE observables SET tlp_override_reason = 'why'")
        connection.exec_driver_sql(
            "UPDATE observables SET tlp_override = 'clear', tlp_override_reason = 'ok', "
            f"tlp_override_set_at = CURRENT_TIMESTAMP, tlp_override_set_by_id = '{ids['user']}'"
        )

        tag_id = uuid.uuid4().hex
        connection.exec_driver_sql(f"INSERT INTO tags (id, name) VALUES ('{tag_id}', 'apt')")
        _fails(connection, f"INSERT INTO tags (id, name) VALUES ('{uuid.uuid4().hex}', 'apt')")
        connection.exec_driver_sql(
            f"INSERT INTO observable_tags VALUES ('{ids['obs']}', '{tag_id}')"
        )
        connection.exec_driver_sql(
            f"INSERT INTO export_profile_tags VALUES ('{ids['profile']}', '{tag_id}')"
        )
        # RESTRICT: a tag a profile filters on cannot be deleted.
        _fails(connection, f"DELETE FROM tags WHERE id = '{tag_id}'")

        _run(migration, connection, "downgrade")
        assert not NEW_TABLES & set(sa.inspect(connection).get_table_names())
        assert _columns(connection, "feeds") == {"id", "name"}
        assert _columns(connection, "reports") == {"id", "title"}
        assert _columns(connection, "observables") == {"id", "value"}
        assert _columns(connection, "export_profiles") == {"id", "name"}
        assert connection.exec_driver_sql("SELECT count(*) FROM observables").scalar() == 1

        _run(migration, connection, "upgrade")
        assert _columns(connection, "observables") >= OBSERVABLE_COLUMNS
        assert connection.exec_driver_sql("SELECT manual_tlp FROM observables").scalar() is None
