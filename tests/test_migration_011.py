"""Migration 011 (AI usage accounting) on SQLite: up, down, up; and model parity."""

from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy.exc import IntegrityError

from cti.models.ai_usage import AiModelPricing, AiUsagePolicy, AiUsageRecord

MIGRATION = Path(__file__).resolve().parents[1] / "alembic" / "versions" / "011_add_ai_usage.py"
TABLES = {"ai_usage_policy", "ai_model_pricing", "ai_usage_records"}
RECORD_COLUMNS = {
    "id",
    "actor_user_id",
    "actor_label",
    "action",
    "provider",
    "model",
    "status",
    "billable",
    "started_at",
    "completed_at",
    "latency_ms",
    "input_tokens",
    "output_tokens",
    "usage_source",
    "reserved_usd",
    "cost_usd",
    "cost_source",
    "error_category",
    "retry_of",
}
RECORD_NULLABLE = {
    "actor_user_id",
    "actor_label",
    "completed_at",
    "latency_ms",
    "input_tokens",
    "output_tokens",
    "reserved_usd",
    "cost_usd",
    "error_category",
    "retry_of",
}
RECORD_INDEXES = {
    "ix_ai_usage_records_started_at": ["started_at"],
    "ix_ai_usage_records_provider_model": ["provider", "model", "started_at"],
}


def load_migration():  # type: ignore[no-untyped-def]
    spec = importlib.util.spec_from_file_location("cti_test_migration_011", MIGRATION)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run(migration, connection: sa.Connection, direction: str) -> None:  # type: ignore[no-untyped-def]
    with Operations.context(MigrationContext.configure(connection)):
        getattr(migration, direction)()


def _insert_record(connection: sa.Connection, **overrides: object) -> str:
    row: dict[str, object] = {
        "id": uuid.uuid4().hex,
        "action": "inference_test",
        "provider": "openai",
        "model": "gpt-test",
        "status": "reserved",
        "billable": "unknown",
        "started_at": "2026-11-02 10:00:00",
        "usage_source": "unknown",
        "cost_source": "unknown",
    }
    row.update(overrides)
    columns = ", ".join(row)
    params = ", ".join(f":{name}" for name in row)
    connection.execute(sa.text(f"INSERT INTO ai_usage_records ({columns}) VALUES ({params})"), row)
    return str(row["id"])


def _record_fails(connection: sa.Connection, **overrides: object) -> None:
    with pytest.raises(IntegrityError), connection.begin_nested():
        _insert_record(connection, **overrides)


def _policy_update_fails(connection: sa.Connection, assignment: str) -> None:
    with pytest.raises(IntegrityError), connection.begin_nested():
        connection.execute(sa.text(f"UPDATE ai_usage_policy SET {assignment} WHERE id = 1"))


def test_migration_011_up_down_up_on_sqlite() -> None:
    migration = load_migration()
    assert migration.revision == "011"
    assert migration.down_revision == "010"

    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys = ON")
        connection.exec_driver_sql("CREATE TABLE users (id CHAR(32) PRIMARY KEY)")

        _run(migration, connection, "upgrade")

        inspector = sa.inspect(connection)
        assert set(inspector.get_table_names()) >= TABLES
        columns = {c["name"]: c for c in inspector.get_columns("ai_usage_records")}
        assert set(columns) == RECORD_COLUMNS
        assert {name for name, c in columns.items() if c["nullable"]} == RECORD_NULLABLE
        indexes = {i["name"]: i["column_names"] for i in inspector.get_indexes("ai_usage_records")}
        assert indexes == RECORD_INDEXES
        [fk] = inspector.get_foreign_keys("ai_usage_records")
        assert fk["referred_table"] == "users"
        assert fk["constrained_columns"] == ["actor_user_id"]
        assert fk["options"].get("ondelete") == "SET NULL"
        pricing_pk = inspector.get_pk_constraint("ai_model_pricing")["constrained_columns"]
        assert pricing_pk == ["provider", "model"]

        # The singleton exists with the contract defaults.
        policy = connection.execute(sa.text("SELECT * FROM ai_usage_policy")).mappings().all()
        assert len(policy) == 1
        assert {k: v for k, v in policy[0].items() if k != "updated_at"} == {
            "id": 1,
            "monthly_budget_usd": None,
            "max_output_tokens": 1024,
            "max_concurrent_requests": 2,
            "max_requests_per_minute": 10,
            "unpriced_model_policy": "block",
        }
        assert policy[0]["updated_at"] is not None
        # No built-in price table ships.
        assert connection.execute(sa.text("SELECT count(*) FROM ai_model_pricing")).scalar() == 0

        # Policy ranges and the singleton are enforced.
        for assignment in (
            "max_output_tokens = 0",
            "max_output_tokens = 32001",
            "max_concurrent_requests = 0",
            "max_concurrent_requests = 51",
            "max_requests_per_minute = 0",
            "max_requests_per_minute = 601",
            "unpriced_model_policy = 'maybe'",
            "monthly_budget_usd = -1",
        ):
            _policy_update_fails(connection, assignment)
        with pytest.raises(IntegrityError), connection.begin_nested():
            connection.execute(sa.text("INSERT INTO ai_usage_policy (id) VALUES (2)"))

        with pytest.raises(IntegrityError), connection.begin_nested():
            connection.execute(
                sa.text(
                    "INSERT INTO ai_model_pricing (provider, model, input_usd_per_mtok, "
                    "output_usd_per_mtok) VALUES ('openai', 'm', -1, 0)"
                )
            )

        # Record enumerations; unknown values stay NULL.
        record_id = _insert_record(connection)
        stored = connection.execute(
            sa.text(
                "SELECT input_tokens, output_tokens, cost_usd, reserved_usd "
                "FROM ai_usage_records WHERE id = :id"
            ),
            {"id": record_id},
        ).one()
        assert tuple(stored) == (None, None, None, None)
        for status in ("succeeded", "failed", "cancelled"):
            _insert_record(connection, status=status)
        for billable in ("yes", "no"):
            _insert_record(connection, billable=billable)
        _insert_record(connection, usage_source="provider_reported", cost_source="estimated")
        _record_fails(connection, action="list_models")
        _record_fails(connection, status="done")
        _record_fails(connection, billable="maybe")
        _record_fails(connection, usage_source="estimated")
        _record_fails(connection, cost_source="provider_reported")
        _record_fails(connection, input_tokens=-1)
        _record_fails(connection, started_at=None)

        # Deleting the actor keeps the record and nulls the link.
        user_id = uuid.uuid4().hex
        connection.execute(sa.text("INSERT INTO users (id) VALUES (:id)"), {"id": user_id})
        linked = _insert_record(connection, actor_user_id=user_id, actor_label="alice")
        connection.execute(sa.text("DELETE FROM users WHERE id = :id"), {"id": user_id})
        row = connection.execute(
            sa.text("SELECT actor_user_id, actor_label FROM ai_usage_records WHERE id = :id"),
            {"id": linked},
        ).one()
        assert tuple(row) == (None, "alice")

        _run(migration, connection, "downgrade")
        assert not TABLES & set(sa.inspect(connection).get_table_names())
        assert "users" in sa.inspect(connection).get_table_names()

        _run(migration, connection, "upgrade")
        assert connection.exec_driver_sql("SELECT count(*) FROM ai_usage_records").scalar() == 0
        assert connection.exec_driver_sql("SELECT count(*) FROM ai_usage_policy").scalar() == 1


def _checks(table: sa.Table) -> set[str]:
    return {str(c.name) for c in table.constraints if isinstance(c, sa.CheckConstraint)}


def test_models_match_migration() -> None:
    """The ORM tables used by the app (and test create_all) mirror revision 011."""
    migration = load_migration()
    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE users (id CHAR(32) PRIMARY KEY)")
        _run(migration, connection, "upgrade")
        migrated = sa.MetaData()
        migrated.reflect(connection, only=sorted(TABLES))

    for model in (AiUsagePolicy, AiModelPricing, AiUsageRecord):
        table = model.__table__
        assert isinstance(table, sa.Table)
        reflected = migrated.tables[table.name]
        assert set(table.columns.keys()) == set(reflected.columns.keys()), table.name
        for name, column in table.columns.items():
            assert column.nullable == reflected.columns[name].nullable, (table.name, name)
            assert column.primary_key == reflected.columns[name].primary_key, (table.name, name)

    record = AiUsageRecord.__table__
    assert {i.name: [c.name for c in i.columns] for i in record.indexes} == RECORD_INDEXES
    assert _checks(record) == {
        "ck_ai_usage_records_action",
        "ck_ai_usage_records_status",
        "ck_ai_usage_records_billable",
        "ck_ai_usage_records_usage_source",
        "ck_ai_usage_records_cost_source",
        "ck_ai_usage_records_tokens",
    }
    assert _checks(AiUsagePolicy.__table__) == {
        "ck_ai_usage_policy_singleton",
        "ck_ai_usage_policy_budget",
        "ck_ai_usage_policy_max_output",
        "ck_ai_usage_policy_concurrency",
        "ck_ai_usage_policy_rate",
        "ck_ai_usage_policy_unpriced",
    }
    assert _checks(AiModelPricing.__table__) == {
        "ck_ai_model_pricing_input",
        "ck_ai_model_pricing_output",
    }


def test_new_error_categories_stay_out_of_the_check_constraint() -> None:
    """Guardrail categories never occur on ``check`` (contract)."""
    from cti.models.ai import AiProviderConfig

    [constraint] = [
        c
        for c in AiProviderConfig.__table__.constraints
        if isinstance(c, sa.CheckConstraint) and c.name == "ck_ai_providers_last_check_category"
    ]
    text = str(constraint.sqltext)
    for category in (
        "budget_exceeded",
        "concurrency_limit",
        "local_rate_limited",
        "model_blocked_unpriced",
        "sharing_forbidden",
        "sharing_not_approved",
    ):
        assert category not in text
