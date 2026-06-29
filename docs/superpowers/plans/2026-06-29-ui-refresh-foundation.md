# UI Refresh — Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the shared backend + frontend foundation that all five redesigned screens depend on, so each screen plan can be implemented and shipped independently afterward.

**Architecture:** Two halves. **Backend** adds the data the redesign draws but the API doesn't yet expose — a preserved `native_confidence` per source (fixing a latent compounding-decay bug in the process), a confidence-distribution + 24h-error block on `/stats`, and three new read-only config fields surfaced through `/settings/config`. **Frontend** replaces the generic shadcn-blue theme with the brand palette (full dark/light token system + working theme toggle), adds the three missing UI primitives (Slider, Popover, Tabs), installs the icon/chart/font dependencies, and updates the TypeScript types to match the new API fields.

**Tech Stack:** Backend — FastAPI, SQLAlchemy 2 (async), Alembic, pydantic-settings, pytest + pytest-asyncio (SQLite in-memory for tests). Frontend — React 18 + TypeScript + Vite, Tailwind (CSS-variable tokens, `darkMode: 'class'`), react-query, react-router, Vitest + happy-dom.

## Global Constraints

- **No parallel styling system.** Express everything through Tailwind + the existing CSS-variable token system and the existing `components/ui/` primitives. Do not ship the prototype HTML.
- **Both themes are mandatory** and fully specified by exact hex values (see Task 8). Dark is the default theme.
- **Mono/sans split is a core part of the look:** `Hanken Grotesk` for UI, `JetBrains Mono` for all observable values, hashes, IPs, numbers/counts, cron strings, key prefixes, and raw JSON.
- **Roles are `admin` / `user` only** — do not introduce Analyst/Read-only. (UI relabels to these two.)
- **General settings are read-only** projections of env vars — never writable via API.
- **Decay model is linear** (`max(floor, native − weeks_stale·rate)`), not half-life. Any UI caption must say so.
- Existing dependency floors: React 18.3, react-router 6.28, react-query 5.62, Tailwind 3.4, Vite 5.4, TypeScript 5.6. Do not bump majors.
- Every backend test uses `@pytest.mark.asyncio` and the `client` / `db_session` fixtures from `tests/conftest.py`. Run backend tests with `uv run --extra dev pytest`; frontend tests with `npm run test` (Vitest) inside `frontend/`.

---

## File Structure

**Backend (modify):**
- `src/cti/models/feed.py` — portable JSON variant for `config` (Task 0, baseline unblock).
- `src/cti/models/observable_source.py` — add `native_confidence` column.
- `src/cti/services/observable_service.py` — set `native_confidence` on ingest upsert.
- `src/cti/services/confidence.py` — decay *from* `native_confidence` (idempotent; fixes compounding bug).
- `src/cti/schemas/observable.py` — expose `native_confidence` in source response.
- `src/cti/api/v1/stats.py` — add `confidence_distribution` + `feed_errors_24h`.
- `src/cti/core/config.py` — add `INSTANCE_NAME`, `OBSERVABLE_RETENTION_DAYS`, `DEFAULT_EXPORT_FORMAT`.
- `src/cti/api/v1/settings.py` — surface the three new fields in `GET /config`.
- `alembic/versions/003_add_native_confidence.py` — **create** migration.
- `.env.example` — document the three new vars.

**Frontend (modify/create):**
- `frontend/package.json` — add `@phosphor-icons/react`, `recharts`.
- `frontend/index.html` — add font `<link>`s; remove hardcoded `class="dark"`.
- `frontend/src/index.css` — replace token palette (both themes) + font-family + categorical/confidence vars.
- `frontend/tailwind.config.js` — map new color tokens + font families.
- `frontend/src/contexts/ThemeContext.tsx` — **create** ThemeProvider + `useTheme`.
- `frontend/src/components/ui/Slider.tsx` — **create**.
- `frontend/src/components/ui/Popover.tsx` — **create**.
- `frontend/src/components/ui/Tabs.tsx` — **create**.
- `frontend/src/components/common/EmergentLogo.tsx` — recolor inner network to brand.
- `frontend/src/types/{observable,dashboard,settings}.ts` — add new fields.
- `frontend/src/main.tsx` — wrap app in `ThemeProvider`.

---

## Task 0: Fix JSONB-on-SQLite so the test suite runs (baseline unblock)

**Context:** The test suite (`tests/conftest.py`) runs on SQLite, but `Feed.config` is typed `JSONB` (Postgres-only), which SQLite cannot compile — so `Base.metadata.create_all` fails and **every** schema-building test errors on a clean checkout. This blocks all backend tasks below. The fix is a portable type that renders `JSON` on SQLite and stays `JSONB` on Postgres (no migration, behavior-preserving on prod).

**Files:**
- Modify: `src/cti/models/feed.py:8,35`

**Interfaces:**
- Produces: `Feed.config` compiles on both SQLite and Postgres. No schema change on Postgres (column stays `JSONB`).

- [ ] **Step 1: Confirm the suite is red for this reason**

Run: `uv run --extra dev pytest tests/test_api/test_health.py -q`
Expected: ERROR — `sqlalchemy.exc.CompileError: ... can't render element of type JSONB`.

- [ ] **Step 2: Make the column type portable**

In `src/cti/models/feed.py`, update the import (`:8`) and the column (`:35`):

```python
from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB
```
```python
    config: Mapped[dict | None] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), default=None
    )
```

(Keep any other existing imports on those lines; only add `JSON` and adjust the `config` column.)

- [ ] **Step 3: Verify the whole suite now runs (and record the true baseline)**

Run: `uv run --extra dev pytest -q`
Expected: collection succeeds and tests run. Record the pass/fail counts as the baseline; all remaining tasks must keep this green.

- [ ] **Step 4: Commit**

```bash
git add src/cti/models/feed.py
git commit -m "fix(models): portable JSON variant for feed.config (unblocks SQLite tests)"
```

---

## Task 1: Preserve `native_confidence` on the source model and ingest

**Files:**
- Modify: `src/cti/models/observable_source.py:31`
- Modify: `src/cti/services/observable_service.py:300-328`
- Test: `tests/test_services/test_native_confidence.py` (create)

**Interfaces:**
- Produces: `ObservableSource.native_confidence: int` (column, default 50). On ingest, `native_confidence` is set to the freshly computed `compute_source_confidence(raw, feed)` and, on conflict, kept at `greatest(existing, incoming)`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_services/test_native_confidence.py
import pytest
from sqlalchemy import select

from cti.feeds.base import RawObservable
from cti.models.feed import Feed, FeedType
from cti.models.observable_source import ObservableSource
from cti.services import observable_service


@pytest.mark.asyncio
async def test_ingest_sets_native_confidence(db_session):
    feed = Feed(name="T", feed_type=FeedType.FILE, default_confidence=70)
    db_session.add(feed)
    await db_session.commit()

    raws = [RawObservable(type="ip-addr", value="1.2.3.4", native_confidence=90)]
    await observable_service.ingest_raw_observables(db_session, feed, raws)

    src = (await db_session.execute(select(ObservableSource))).scalar_one()
    assert src.source_confidence == 90
    assert src.native_confidence == 90
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --extra dev pytest tests/test_services/test_native_confidence.py -v`
Expected: FAIL — `AttributeError: 'ObservableSource' object has no attribute 'native_confidence'` (or the ingest helper name differs; if so, match the real public ingest entrypoint in `observable_service.py` and update the call).

- [ ] **Step 3: Add the column to the model**

In `src/cti/models/observable_source.py`, directly after the `source_confidence` line (`:31`):

```python
    source_confidence: Mapped[int] = mapped_column(Integer, default=50)
    native_confidence: Mapped[int] = mapped_column(Integer, default=50)
```

- [ ] **Step 4: Set it on ingest**

In `src/cti/services/observable_service.py`, in the `source_rows.append({...})` block (`:301-310`), add the `native_confidence` key:

```python
                    source_conf = compute_source_confidence(raw, feed)
                    source_rows.append(
                        {
                            "id": uuid.uuid4(),
                            "observable_id": obs_id,
                            "feed_id": feed.id,
                            "source_confidence": source_conf,
                            "native_confidence": source_conf,
                            "first_seen_by_feed": raw.first_seen or now,
                            "last_seen_by_feed": raw.last_seen or now,
                        }
                    )
```

And in the `on_conflict_do_update(set_={...})` block (`:318-327`), keep native at the max ever seen:

```python
                        set_={
                            "source_confidence": func.greatest(
                                ObservableSource.__table__.c.source_confidence,
                                src_stmt.excluded.source_confidence,
                            ),
                            "native_confidence": func.greatest(
                                ObservableSource.__table__.c.native_confidence,
                                src_stmt.excluded.native_confidence,
                            ),
                            "last_seen_by_feed": func.greatest(
                                ObservableSource.__table__.c.last_seen_by_feed,
                                src_stmt.excluded.last_seen_by_feed,
                            ),
                        },
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run --extra dev pytest tests/test_services/test_native_confidence.py -v`
Expected: PASS. (Tests build tables from the model via `Base.metadata.create_all`, so no migration is needed for tests.)

- [ ] **Step 6: Commit**

```bash
git add src/cti/models/observable_source.py src/cti/services/observable_service.py tests/test_services/test_native_confidence.py
git commit -m "feat(confidence): preserve native_confidence per source on ingest"
```

---

## Task 2: Decay from `native_confidence` (idempotent — fixes compounding-decay bug)

**Files:**
- Modify: `src/cti/services/confidence.py:66-85`
- Test: `tests/test_services/test_decay_from_native.py` (create)

**Interfaces:**
- Consumes: `ObservableSource.native_confidence` (Task 1).
- Produces: `apply_confidence_decay` computes `source_confidence = max(floor, native_confidence − weeks_stale·rate)` and is idempotent across repeated runs. `native_confidence` is never mutated.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_services/test_decay_from_native.py
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from cti.models.feed import Feed, FeedType
from cti.models.observable import Observable, ObservableType
from cti.models.observable_source import ObservableSource
from cti.services.confidence import DecaySettings, apply_confidence_decay


async def _stale_source(db, days_stale: int, native: int = 90):
    feed = Feed(name="F", feed_type=FeedType.FILE, default_confidence=50)
    obs = Observable(type=ObservableType.IP_ADDR, value="9.9.9.9", confidence_score=native)
    db.add_all([feed, obs])
    await db.commit()
    seen = datetime.now(UTC) - timedelta(days=days_stale)
    src = ObservableSource(
        observable_id=obs.id, feed_id=feed.id,
        source_confidence=native, native_confidence=native,
        first_seen_by_feed=seen, last_seen_by_feed=seen,
    )
    db.add(src)
    await db.commit()
    return src.id


@pytest.mark.asyncio
async def test_decay_is_idempotent_and_native_preserved(db_session):
    src_id = await _stale_source(db_session, days_stale=37, native=90)  # 1 week past 30d cutoff
    settings = DecaySettings(enabled=True, decay_days=30, decay_rate=5, decay_floor=10)

    await apply_confidence_decay(db_session, settings)
    src = (await db_session.execute(
        select(ObservableSource).where(ObservableSource.id == src_id))).scalar_one()
    first = src.source_confidence
    assert first == 85          # 90 - (1 week * 5)
    assert src.native_confidence == 90

    # Running again the same day must NOT decay further (the old bug double-subtracted).
    await apply_confidence_decay(db_session, settings)
    src = (await db_session.execute(
        select(ObservableSource).where(ObservableSource.id == src_id))).scalar_one()
    assert src.source_confidence == first
    assert src.native_confidence == 90
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --extra dev pytest tests/test_services/test_decay_from_native.py -v`
Expected: FAIL — second run decays again (e.g. `80 != 85`), because the current code subtracts from the already-decayed `source_confidence`.

- [ ] **Step 3: Rewrite the decay loop to compute from native**

In `src/cti/services/confidence.py`, replace the query filter and loop (`:66-85`):

```python
    # Find stale sources whose NATIVE score still has room to decay.
    result = await db.execute(
        select(ObservableSource).where(
            ObservableSource.last_seen_by_feed < stale_cutoff,
            ObservableSource.native_confidence > settings.decay_floor,
        )
    )

    affected_observable_ids: set[uuid.UUID] = set()

    for source in result.scalars():
        days_stale = (now - source.last_seen_by_feed).days
        weeks_stale = max(1, (days_stale - settings.decay_days) // 7 + 1)
        new_conf = max(
            settings.decay_floor,
            source.native_confidence - (weeks_stale * settings.decay_rate),
        )
        if new_conf != source.source_confidence:
            source.source_confidence = new_conf
            affected_observable_ids.add(source.observable_id)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --extra dev pytest tests/test_services/test_decay_from_native.py -v`
Expected: PASS.

- [ ] **Step 5: Run the full confidence suite for regressions**

Run: `uv run --extra dev pytest tests/test_services -v`
Expected: PASS (no other decay tests broken).

- [ ] **Step 6: Commit**

```bash
git add src/cti/services/confidence.py tests/test_services/test_decay_from_native.py
git commit -m "fix(confidence): decay from native_confidence, idempotent (fixes compounding decay)"
```

---

## Task 3: Expose `native_confidence` in the observable source schema

**Files:**
- Modify: `src/cti/schemas/observable.py:13-20`
- Test: `tests/test_api/test_observables.py` (append one test)

**Interfaces:**
- Produces: `ObservableSourceResponse.native_confidence: int` — present in every `GET /api/v1/observables` and `GET /api/v1/observables/{id}` source entry.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_api/test_observables.py
@pytest.mark.asyncio
async def test_observable_source_exposes_native_confidence(client, db_session):
    from cti.feeds.base import RawObservable
    from cti.models.feed import Feed, FeedType
    from cti.services import observable_service

    feed = Feed(name="NF", feed_type=FeedType.FILE, default_confidence=80)
    db_session.add(feed)
    await db_session.commit()
    await observable_service.ingest_raw_observables(
        db_session, feed, [RawObservable(type="ip-addr", value="5.5.5.5", native_confidence=80)]
    )

    resp = await client.get("/api/v1/observables", params={"q": "5.5.5.5"})
    assert resp.status_code == 200
    src = resp.json()["items"][0]["sources"][0]
    assert src["native_confidence"] == 80
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --extra dev pytest tests/test_api/test_observables.py::test_observable_source_exposes_native_confidence -v`
Expected: FAIL — `KeyError: 'native_confidence'`.

- [ ] **Step 3: Add the field to the schema**

In `src/cti/schemas/observable.py`, add to `ObservableSourceResponse` (after `source_confidence`, `:16`):

```python
class ObservableSourceResponse(BaseModel):
    feed_id: uuid.UUID
    feed_name: str
    source_confidence: int
    native_confidence: int
    first_seen_by_feed: datetime
    last_seen_by_feed: datetime

    model_config = {"from_attributes": True}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --extra dev pytest tests/test_api/test_observables.py::test_observable_source_exposes_native_confidence -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/cti/schemas/observable.py tests/test_api/test_observables.py
git commit -m "feat(api): expose native_confidence in observable source response"
```

---

## Task 4: Alembic migration for `native_confidence`

**Files:**
- Create: `alembic/versions/003_add_native_confidence.py`

**Interfaces:**
- Consumes: revision `002_add_users_auth` (current head).
- Produces: `observable_sources.native_confidence INTEGER NOT NULL DEFAULT 50`, backfilled from `source_confidence`.

- [ ] **Step 1: Confirm current head**

Run: `uv run alembic heads`
Expected: shows `002` (the `002_add_users_auth` revision) as head. Use its real revision id as `down_revision` below.

- [ ] **Step 2: Write the migration**

```python
# alembic/versions/003_add_native_confidence.py
"""add native_confidence to observable_sources

Revision ID: 003_add_native_confidence
Revises: 002_add_users_auth
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "003_add_native_confidence"
down_revision = "002_add_users_auth"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "observable_sources",
        sa.Column("native_confidence", sa.Integer(), nullable=False, server_default="50"),
    )
    # Backfill from the current (possibly already-decayed) value — best available origin.
    op.execute("UPDATE observable_sources SET native_confidence = source_confidence")


def downgrade() -> None:
    op.drop_column("observable_sources", "native_confidence")
```

> Note: `down_revision` must match the literal `revision = ...` string inside `002_add_users_auth.py`. If it differs from `002_add_users_auth`, use the actual value from Step 1.

- [ ] **Step 3: Apply the migration against the dev DB**

Run: `docker compose exec api alembic upgrade head` (or `uv run alembic upgrade head` with a local Postgres).
Expected: `Running upgrade 002... -> 003_add_native_confidence`.

- [ ] **Step 4: Verify column exists**

Run: `docker compose exec postgres psql -U cti -d cti -c "\d observable_sources"`
Expected: lists `native_confidence | integer | not null`.

- [ ] **Step 5: Commit**

```bash
git add alembic/versions/003_add_native_confidence.py
git commit -m "chore(db): migration for native_confidence column"
```

---

## Task 5: Add confidence distribution + 24h feed errors to `/stats`

**Files:**
- Modify: `src/cti/api/v1/stats.py`
- Test: `tests/test_api/test_stats.py` (create)

**Interfaces:**
- Produces: `/api/v1/stats` response gains
  `"confidence_distribution": {"critical": int, "high": int, "medium": int, "low": int}` (bands 80–100 / 60–79 / 40–59 / 0–39) and `"feed_errors_24h": int`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_api/test_stats.py
import pytest

from cti.models.observable import Observable, ObservableType


@pytest.mark.asyncio
async def test_stats_includes_distribution_and_errors(client, db_session):
    db_session.add_all([
        Observable(type=ObservableType.IP_ADDR, value="1.1.1.1", confidence_score=95),  # critical
        Observable(type=ObservableType.IP_ADDR, value="1.1.1.2", confidence_score=65),  # high
        Observable(type=ObservableType.IP_ADDR, value="1.1.1.3", confidence_score=45),  # medium
        Observable(type=ObservableType.IP_ADDR, value="1.1.1.4", confidence_score=10),  # low
    ])
    await db_session.commit()

    resp = await client.get("/api/v1/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert data["confidence_distribution"] == {"critical": 1, "high": 1, "medium": 1, "low": 1}
    assert data["feed_errors_24h"] == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --extra dev pytest tests/test_api/test_stats.py -v`
Expected: FAIL — `KeyError: 'confidence_distribution'`. (If a cached value is returned, the test DB is fresh per-test so the cache key is empty; if flaky, the cache is Redis and may be unavailable in tests — `cache_get` returns `None` on failure, which is fine.)

- [ ] **Step 3: Add the imports**

In `src/cti/api/v1/stats.py`, extend the SQLAlchemy import (`:8`):

```python
from sqlalchemy import and_, case, func, select
```

- [ ] **Step 4: Compute the new blocks before assembling `result`**

In `src/cti/api/v1/stats.py`, after the feed-health loop and before `result = {...}` (`:84`), add:

```python
    # Confidence distribution (band counts)
    dist_result = await db.execute(
        select(
            func.sum(case((Observable.confidence_score >= 80, 1), else_=0)),
            func.sum(case((and_(Observable.confidence_score >= 60,
                                Observable.confidence_score < 80), 1), else_=0)),
            func.sum(case((and_(Observable.confidence_score >= 40,
                                Observable.confidence_score < 60), 1), else_=0)),
            func.sum(case((Observable.confidence_score < 40, 1), else_=0)),
        )
    )
    crit, high, med, low = dist_result.one()
    confidence_distribution = {
        "critical": int(crit or 0),
        "high": int(high or 0),
        "medium": int(med or 0),
        "low": int(low or 0),
    }

    # Feed errors in the last 24h
    errors_result = await db.execute(
        select(func.count(FeedRun.id)).where(
            FeedRun.status == FeedRunStatus.FAILURE,
            func.coalesce(FeedRun.completed_at, FeedRun.started_at) >= cutoff_24h,
        )
    )
    feed_errors_24h = errors_result.scalar_one()
```

- [ ] **Step 5: Add both keys to the `result` dict**

In the `result = {...}` literal (`:85-92`), add:

```python
        "last_24h_ingested": last_24h_ingested,
        "confidence_distribution": confidence_distribution,
        "feed_errors_24h": feed_errors_24h,
        "feeds_health": feeds_health,
```

- [ ] **Step 6: Run test to verify it passes**

Run: `uv run --extra dev pytest tests/test_api/test_stats.py -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/cti/api/v1/stats.py tests/test_api/test_stats.py
git commit -m "feat(stats): add confidence distribution and 24h feed-error count"
```

---

## Task 6: Add read-only config fields (instance name, retention, export format)

**Files:**
- Modify: `src/cti/core/config.py:44-49`
- Modify: `src/cti/api/v1/settings.py:110-121`
- Modify: `.env.example`
- Test: `tests/test_api/test_settings.py` (append)

**Interfaces:**
- Produces: `GET /api/v1/settings/config` additionally returns `instance_name`, `observable_retention_days`, `default_export_format`. All env-driven via `config.py`, never writable.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_api/test_settings.py
@pytest.mark.asyncio
async def test_config_exposes_instance_settings(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/settings/config")
    assert resp.status_code == 200
    data = resp.json()
    assert data["instance_name"] == "EmergentCTI"
    assert data["observable_retention_days"] == 180
    assert data["default_export_format"] == "text"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --extra dev pytest tests/test_api/test_settings.py::test_config_exposes_instance_settings -v`
Expected: FAIL — `KeyError: 'instance_name'`.

- [ ] **Step 3: Add the settings fields**

In `src/cti/core/config.py`, after the Confidence-decay block (`:49`):

```python
    # ── Instance / display settings (read-only, env-driven) ──────────────
    INSTANCE_NAME: str = "EmergentCTI"
    OBSERVABLE_RETENTION_DAYS: int = 180
    DEFAULT_EXPORT_FORMAT: str = "text"
```

- [ ] **Step 4: Surface them in the config endpoint**

In `src/cti/api/v1/settings.py`, extend the `get_config` return dict (`:115-121`):

```python
    return {
        "confidence_decay_enabled": settings.CONFIDENCE_DECAY_ENABLED,
        "confidence_decay_days": settings.CONFIDENCE_DECAY_DAYS,
        "confidence_decay_rate": settings.CONFIDENCE_DECAY_RATE,
        "confidence_decay_floor": settings.CONFIDENCE_DECAY_FLOOR,
        "confidence_decay_interval_hours": settings.CONFIDENCE_DECAY_INTERVAL_HOURS,
        "instance_name": settings.INSTANCE_NAME,
        "observable_retention_days": settings.OBSERVABLE_RETENTION_DAYS,
        "default_export_format": settings.DEFAULT_EXPORT_FORMAT,
    }
```

- [ ] **Step 5: Document in `.env.example`**

Add to `.env.example` under a new section:

```bash
# Instance / display (read-only in the UI; change here + restart)
INSTANCE_NAME=EmergentCTI
OBSERVABLE_RETENTION_DAYS=180
DEFAULT_EXPORT_FORMAT=text
```

> Honesty note for the Settings screen: `OBSERVABLE_RETENTION_DAYS` is currently a *displayed policy value only* — no job enforces it yet. Enforcement (a retention/TTL purge) is a separate follow-up, not part of this plan.

- [ ] **Step 6: Run test to verify it passes**

Run: `uv run --extra dev pytest tests/test_api/test_settings.py::test_config_exposes_instance_settings -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/cti/core/config.py src/cti/api/v1/settings.py .env.example tests/test_api/test_settings.py
git commit -m "feat(settings): expose instance name, retention, export format (read-only)"
```

---

## Task 7: Install icon, chart, and font dependencies

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/index.html`

**Interfaces:**
- Produces: `@phosphor-icons/react` and `recharts` importable; Hanken Grotesk + JetBrains Mono available as CSS font families.

- [ ] **Step 1: Install the npm deps**

Run (in `frontend/`):
```bash
npm install @phosphor-icons/react recharts
```
Expected: both added to `dependencies` in `frontend/package.json`.

- [ ] **Step 2: Add the font links**

In `frontend/index.html`, inside `<head>` (before the existing stylesheet/module), add:

```html
    <link rel="preconnect" href="https://fonts.googleapis.com" />
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
    <link
      href="https://fonts.googleapis.com/css2?family=Hanken+Grotesk:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap"
      rel="stylesheet"
    />
```

- [ ] **Step 3: Verify the build still resolves**

Run (in `frontend/`): `npm run build`
Expected: build succeeds (no missing-module errors).

- [ ] **Step 4: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/index.html
git commit -m "chore(frontend): add phosphor-icons, recharts, brand fonts"
```

---

## Task 8: Replace the theme token palette (both themes) and Tailwind mapping

**Files:**
- Modify: `frontend/src/index.css`
- Modify: `frontend/tailwind.config.js`

**Interfaces:**
- Produces: CSS tokens now hold **hex** values (not HSL triplets). Existing semantic Tailwind names (`background`, `foreground`, `card`, `primary`, `border`, `muted`) keep working but resolve to the brand palette. New names available: `surface2`, `surface3`, `hover`, `borderStrong`, `brand`, `brand2`, plus `cat-*` (categorical) and `conf-*` (confidence band) scales. Font families `font-sans` (Hanken Grotesk) and `font-mono` (JetBrains Mono).

> Because token values switch from HSL triplets to hex, Tailwind color values change from `hsl(var(--x))` to `var(--x)`. Both files change together.

- [ ] **Step 1: Rewrite the token blocks in `frontend/src/index.css`**

Replace the entire `@layer base { :root {...} .dark {...} }` block (lines `5-51`) with:

```css
@layer base {
  :root {
    /* Light theme */
    --background: #f2f4f8;
    --foreground: #10141d;
    --surface: #ffffff;
    --surface-2: #f7f9fc;
    --surface-3: #eef1f6;
    --hover: #f4f7fa;
    --card: var(--surface);
    --popover: var(--surface);
    --border: #e5e9f0;
    --border-strong: #d3dae4;
    --muted: var(--surface-3);
    --muted-foreground: #576175;
    --text-3: #8a94a6;
    --primary: #a31f24;
    --brand: #a31f24;
    --brand-2: #851a1d;
    --on-brand: #ffffff;
    --destructive: #d23a3f;

    /* Categorical (light) */
    --cat-green: #1f9d63;
    --cat-blue: #2f6fe0;
    --cat-purple: #7a4fd6;
    --cat-orange: #d9710a;
    --cat-pink: #cf4f93;
    --cat-yellow: #b8860b;

    /* Confidence bands (light) */
    --conf-critical: #d23a3f;
    --conf-high: #d9710a;
    --conf-medium: #b8860b;
    --conf-low: #6b7585;

    --radius: 0.8125rem; /* 13px cards */
  }

  .dark {
    /* Dark theme (default) */
    --background: #0a0d13;
    --foreground: #eef1f7;
    --surface: #10141c;
    --surface-2: #151a23;
    --surface-3: #1b212c;
    --hover: #181e28;
    --card: var(--surface);
    --popover: var(--surface);
    --border: #222a37;
    --border-strong: #2f3a4a;
    --muted: var(--surface-3);
    --muted-foreground: #9aa6b8;
    --text-3: #646f82;
    --primary: #e0484e;
    --brand: #e0484e;
    --brand-2: #b22f34;
    --on-brand: #ffffff;
    --destructive: #ef5350;

    /* Categorical (dark) */
    --cat-green: #2fbf71;
    --cat-blue: #4b8bf5;
    --cat-purple: #9b6dff;
    --cat-orange: #f0883e;
    --cat-pink: #ec6aa6;
    --cat-yellow: #e0a92a;

    /* Confidence bands (dark) */
    --conf-critical: #ef5350;
    --conf-high: #ff8a3d;
    --conf-medium: #ffc24b;
    --conf-low: #8b95a6;

    --radius: 0.8125rem;
  }
}

@layer base {
  * { @apply border-border; }
  body {
    @apply bg-background text-foreground;
    font-family: 'Hanken Grotesk', ui-sans-serif, system-ui, sans-serif;
    font-size: 14px;
    line-height: 1.5;
    -webkit-font-smoothing: antialiased;
  }
}
```

Keep the existing scrollbar + `@keyframes pulse-dot` rules below (update the scrollbar `hsl(...)` literals to the hex `--surface`/`--surface-3` if desired; optional).

- [ ] **Step 2: Rewrite the color/border/font mapping in `frontend/tailwind.config.js`**

Replace `theme.extend` with:

```js
  theme: {
    extend: {
      colors: {
        background: 'var(--background)',
        foreground: 'var(--foreground)',
        surface: 'var(--surface)',
        surface2: 'var(--surface-2)',
        surface3: 'var(--surface-3)',
        hover: 'var(--hover)',
        card: { DEFAULT: 'var(--card)', foreground: 'var(--foreground)' },
        popover: { DEFAULT: 'var(--popover)', foreground: 'var(--foreground)' },
        primary: { DEFAULT: 'var(--primary)', foreground: 'var(--on-brand)' },
        brand: { DEFAULT: 'var(--brand)', 2: 'var(--brand-2)', foreground: 'var(--on-brand)' },
        muted: { DEFAULT: 'var(--muted)', foreground: 'var(--muted-foreground)' },
        destructive: { DEFAULT: 'var(--destructive)', foreground: '#ffffff' },
        border: 'var(--border)',
        borderStrong: 'var(--border-strong)',
        input: 'var(--surface-2)',
        ring: 'var(--brand)',
        cat: {
          green: 'var(--cat-green)', blue: 'var(--cat-blue)', purple: 'var(--cat-purple)',
          orange: 'var(--cat-orange)', pink: 'var(--cat-pink)', yellow: 'var(--cat-yellow)',
        },
        conf: {
          critical: 'var(--conf-critical)', high: 'var(--conf-high)',
          medium: 'var(--conf-medium)', low: 'var(--conf-low)',
        },
      },
      fontFamily: {
        sans: ['Hanken Grotesk', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'ui-monospace', 'SFMono-Regular', 'monospace'],
      },
      borderRadius: {
        lg: 'var(--radius)',
        md: 'calc(var(--radius) - 4px)',
        sm: 'calc(var(--radius) - 7px)',
      },
    },
  },
```

- [ ] **Step 3: Verify the build and visually smoke-test**

Run (in `frontend/`): `npm run build`
Expected: build succeeds. Then `npm run dev` and confirm the app renders in brand colors (it will still be dark-locked until Task 9).

- [ ] **Step 4: Commit**

```bash
git add frontend/src/index.css frontend/tailwind.config.js
git commit -m "feat(theme): brand palette tokens for dark + light themes"
```

---

## Task 9: ThemeProvider + toggle + persistence

**Files:**
- Create: `frontend/src/contexts/ThemeContext.tsx`
- Modify: `frontend/index.html` (remove `class="dark"`)
- Modify: `frontend/src/main.tsx` (wrap in provider)
- Test: `frontend/src/contexts/ThemeContext.test.tsx` (create)

**Interfaces:**
- Produces: `ThemeProvider` component and `useTheme(): { theme: 'dark' | 'light'; toggle: () => void }`. Applies/removes `.dark` on `document.documentElement`. Persists to `localStorage['theme']`; defaults to `dark` when unset.

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/src/contexts/ThemeContext.test.tsx
import { act, render, screen } from '@testing-library/react';
import { describe, expect, it, beforeEach } from 'vitest';
import { ThemeProvider, useTheme } from './ThemeContext';

function Probe() {
  const { theme, toggle } = useTheme();
  return <button onClick={toggle}>theme:{theme}</button>;
}

describe('ThemeContext', () => {
  beforeEach(() => localStorage.clear());

  it('defaults to dark and toggles to light, updating the html class', () => {
    render(<ThemeProvider><Probe /></ThemeProvider>);
    expect(screen.getByText('theme:dark')).toBeTruthy();
    expect(document.documentElement.classList.contains('dark')).toBe(true);

    act(() => screen.getByRole('button').click());
    expect(screen.getByText('theme:light')).toBeTruthy();
    expect(document.documentElement.classList.contains('dark')).toBe(false);
    expect(localStorage.getItem('theme')).toBe('light');
  });
});
```

> If `@testing-library/react` is not yet a devDependency, add it: `npm install -D @testing-library/react @testing-library/dom`. The repo already uses Vitest + happy-dom.

- [ ] **Step 2: Run test to verify it fails**

Run (in `frontend/`): `npm run test -- ThemeContext`
Expected: FAIL — module `./ThemeContext` not found.

- [ ] **Step 3: Implement the provider**

```tsx
// frontend/src/contexts/ThemeContext.tsx
import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';

type Theme = 'dark' | 'light';
interface ThemeValue { theme: Theme; toggle: () => void; }

const ThemeContext = createContext<ThemeValue | undefined>(undefined);

function getInitialTheme(): Theme {
  const stored = localStorage.getItem('theme');
  return stored === 'light' ? 'light' : 'dark'; // default dark
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<Theme>(getInitialTheme);

  useEffect(() => {
    const root = document.documentElement;
    root.classList.toggle('dark', theme === 'dark');
    localStorage.setItem('theme', theme);
  }, [theme]);

  const toggle = () => setTheme((t) => (t === 'dark' ? 'light' : 'dark'));
  return <ThemeContext.Provider value={{ theme, toggle }}>{children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeValue {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error('useTheme must be used within ThemeProvider');
  return ctx;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run (in `frontend/`): `npm run test -- ThemeContext`
Expected: PASS.

- [ ] **Step 5: Wire into the app and stop hard-locking dark**

In `frontend/index.html`, change `<html lang="en" class="dark">` to `<html lang="en">`.

In `frontend/src/main.tsx`, wrap the root render with `ThemeProvider` (outermost, around the existing `QueryClientProvider`/`BrowserRouter`):

```tsx
import { ThemeProvider } from '@/contexts/ThemeContext';
// ...
  <ThemeProvider>
    {/* existing providers / <App /> */}
  </ThemeProvider>
```

- [ ] **Step 6: Verify no flash + persistence by hand**

Run (in `frontend/`): `npm run dev`. Confirm: default load is dark; toggling persists across reload.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/contexts/ThemeContext.tsx frontend/src/contexts/ThemeContext.test.tsx frontend/index.html frontend/src/main.tsx frontend/package.json
git commit -m "feat(theme): ThemeProvider with toggle and localStorage persistence"
```

---

## Task 10: Slider primitive

**Files:**
- Create: `frontend/src/components/ui/Slider.tsx`
- Test: `frontend/src/components/ui/Slider.test.tsx` (create)

**Interfaces:**
- Produces: `Slider({ value, min, max, step, onChange, className })` — controlled range input styled with brand fill. `onChange(next: number)`.

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/src/components/ui/Slider.test.tsx
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { Slider } from './Slider';

describe('Slider', () => {
  it('emits the numeric value on change', () => {
    const onChange = vi.fn();
    render(<Slider value={20} min={0} max={100} step={5} onChange={onChange} />);
    fireEvent.change(screen.getByRole('slider'), { target: { value: '40' } });
    expect(onChange).toHaveBeenCalledWith(40);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run (in `frontend/`): `npm run test -- Slider`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement**

```tsx
// frontend/src/components/ui/Slider.tsx
import { cn } from '@/lib/utils';

export interface SliderProps {
  value: number;
  min?: number;
  max?: number;
  step?: number;
  onChange: (value: number) => void;
  className?: string;
}

export function Slider({ value, min = 0, max = 100, step = 1, onChange, className }: SliderProps) {
  const pct = ((value - min) / (max - min)) * 100;
  return (
    <input
      type="range"
      role="slider"
      min={min}
      max={max}
      step={step}
      value={value}
      onChange={(e) => onChange(Number(e.target.value))}
      className={cn('h-1.5 w-full cursor-pointer appearance-none rounded-full', className)}
      style={{ background: `linear-gradient(to right, var(--brand) ${pct}%, var(--surface-3) ${pct}%)` }}
    />
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run (in `frontend/`): `npm run test -- Slider`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/ui/Slider.tsx frontend/src/components/ui/Slider.test.tsx
git commit -m "feat(ui): add Slider primitive"
```

---

## Task 11: Popover primitive

**Files:**
- Create: `frontend/src/components/ui/Popover.tsx`
- Test: `frontend/src/components/ui/Popover.test.tsx` (create)

**Interfaces:**
- Produces: `Popover({ trigger, children, align })` — click trigger toggles content; click-away closes (via a backdrop or document listener). Content uses `bg-popover`, `border-border`, shadow.

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/src/components/ui/Popover.test.tsx
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { Popover } from './Popover';

describe('Popover', () => {
  it('opens on trigger click and closes on click-away', () => {
    render(
      <Popover trigger={<button>Export</button>}>
        <div>panel-content</div>
      </Popover>,
    );
    expect(screen.queryByText('panel-content')).toBeNull();
    fireEvent.click(screen.getByText('Export'));
    expect(screen.getByText('panel-content')).toBeTruthy();
    fireEvent.mouseDown(document.body);
    expect(screen.queryByText('panel-content')).toBeNull();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run (in `frontend/`): `npm run test -- Popover`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement**

```tsx
// frontend/src/components/ui/Popover.tsx
import { useEffect, useRef, useState, type ReactNode } from 'react';
import { cn } from '@/lib/utils';

export interface PopoverProps {
  trigger: ReactNode;
  children: ReactNode;
  align?: 'start' | 'end';
  className?: string;
}

export function Popover({ trigger, children, align = 'start', className }: PopoverProps) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', onDown);
    return () => document.removeEventListener('mousedown', onDown);
  }, [open]);

  return (
    <div ref={ref} className="relative inline-block">
      <div onClick={() => setOpen((o) => !o)}>{trigger}</div>
      {open && (
        <div
          className={cn(
            'absolute z-50 mt-2 min-w-[14rem] rounded-md border border-border bg-popover p-1 shadow-lg',
            align === 'end' ? 'right-0' : 'left-0',
            className,
          )}
        >
          {children}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run (in `frontend/`): `npm run test -- Popover`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/ui/Popover.tsx frontend/src/components/ui/Popover.test.tsx
git commit -m "feat(ui): add Popover primitive"
```

---

## Task 12: Tabs primitive

**Files:**
- Create: `frontend/src/components/ui/Tabs.tsx`
- Test: `frontend/src/components/ui/Tabs.test.tsx` (create)

**Interfaces:**
- Produces: `Tabs({ tabs: {key,label}[], active, onChange })` — renders a tab bar; active tab uses brand underline/text. Controlled via `active` + `onChange(key)`.

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/src/components/ui/Tabs.test.tsx
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { Tabs } from './Tabs';

describe('Tabs', () => {
  it('marks the active tab and emits onChange', () => {
    const onChange = vi.fn();
    render(
      <Tabs
        tabs={[{ key: 'sources', label: 'Sources' }, { key: 'raw', label: 'Raw JSON' }]}
        active="sources"
        onChange={onChange}
      />,
    );
    expect(screen.getByRole('tab', { name: 'Sources' }).getAttribute('aria-selected')).toBe('true');
    fireEvent.click(screen.getByRole('tab', { name: 'Raw JSON' }));
    expect(onChange).toHaveBeenCalledWith('raw');
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run (in `frontend/`): `npm run test -- Tabs`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement**

```tsx
// frontend/src/components/ui/Tabs.tsx
import { cn } from '@/lib/utils';

export interface TabItem { key: string; label: string; }
export interface TabsProps {
  tabs: TabItem[];
  active: string;
  onChange: (key: string) => void;
  className?: string;
}

export function Tabs({ tabs, active, onChange, className }: TabsProps) {
  return (
    <div role="tablist" className={cn('flex gap-1 border-b border-border', className)}>
      {tabs.map((t) => {
        const selected = t.key === active;
        return (
          <button
            key={t.key}
            role="tab"
            aria-selected={selected}
            onClick={() => onChange(t.key)}
            className={cn(
              '-mb-px border-b-2 px-3 py-2 text-sm font-semibold transition-colors',
              selected
                ? 'border-brand text-brand'
                : 'border-transparent text-muted-foreground hover:text-foreground',
            )}
          >
            {t.label}
          </button>
        );
      })}
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run (in `frontend/`): `npm run test -- Tabs`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/ui/Tabs.tsx frontend/src/components/ui/Tabs.test.tsx
git commit -m "feat(ui): add Tabs primitive"
```

---

## Task 13: Recolor EmergentLogo inner network to brand

**Files:**
- Modify: `frontend/src/components/common/EmergentLogo.tsx`

**Interfaces:**
- Produces: logo whose hex outline uses `currentColor` (inherits `--foreground`) and whose inner network lines/nodes use `var(--brand)`.

- [ ] **Step 1: Read the current logo and identify the inner-network paths**

Run: open `frontend/src/components/common/EmergentLogo.tsx`. The inner network elements currently use a hardcoded `#85191A`.

- [ ] **Step 2: Replace the hardcoded inner color with the brand token**

Replace every inner-network `stroke="#85191A"` / `fill="#85191A"` with `stroke="var(--brand)"` / `fill="var(--brand)"`, and ensure the hexagon outline uses `stroke="currentColor"`.

- [ ] **Step 3: Verify in both themes**

Run (in `frontend/`): `npm run dev`. Confirm the inner network renders crimson in dark and the darker crimson in light (the token flips automatically), and the hex outline follows text color.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/common/EmergentLogo.tsx
git commit -m "feat(brand): recolor EmergentLogo inner network to brand token"
```

---

## Task 14: Update frontend types for the new API fields

**Files:**
- Modify: `frontend/src/types/observable.ts`
- Modify: `frontend/src/types/dashboard.ts`
- Modify: `frontend/src/types/settings.ts`
- Test: `frontend/src/types/types.test.ts` (create — compile-time assertion)

**Interfaces:**
- Consumes: Tasks 3, 5, 6 (API field additions).
- Produces: `ObservableSource.native_confidence: number`; `DashboardStats.confidence_distribution` + `feed_errors_24h`; `ConfidenceDecayConfig`/config type gains `instance_name`, `observable_retention_days`, `default_export_format`.

- [ ] **Step 1: Write the failing test**

```ts
// frontend/src/types/types.test.ts
import { describe, expect, it } from 'vitest';
import type { ObservableSource } from './observable';
import type { DashboardStats } from './dashboard';
import type { InstanceConfig } from './settings';

describe('type shapes', () => {
  it('carry the new foundation fields', () => {
    const src: ObservableSource = {
      feed_id: 'f', feed_name: 'n', source_confidence: 50, native_confidence: 80,
      first_seen_by_feed: '', last_seen_by_feed: '',
    };
    const stats: Pick<DashboardStats, 'confidence_distribution' | 'feed_errors_24h'> = {
      confidence_distribution: { critical: 1, high: 0, medium: 0, low: 0 },
      feed_errors_24h: 0,
    };
    const cfg: Pick<InstanceConfig, 'instance_name'> = { instance_name: 'EmergentCTI' };
    expect(src.native_confidence + stats.feed_errors_24h).toBe(80);
    expect(cfg.instance_name).toBe('EmergentCTI');
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run (in `frontend/`): `npm run test -- types`
Expected: FAIL — `native_confidence` / `confidence_distribution` / `InstanceConfig` not assignable/exported.

- [ ] **Step 3: Add the fields**

`frontend/src/types/observable.ts` — add to `ObservableSource`:
```ts
  native_confidence: number;
```

`frontend/src/types/dashboard.ts` — add to `DashboardStats`:
```ts
  confidence_distribution: { critical: number; high: number; medium: number; low: number };
  feed_errors_24h: number;
```

`frontend/src/types/settings.ts` — add:
```ts
export interface InstanceConfig extends ConfidenceDecayConfig {
  instance_name: string;
  observable_retention_days: number;
  default_export_format: string;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run (in `frontend/`): `npm run test -- types`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/types/observable.ts frontend/src/types/dashboard.ts frontend/src/types/settings.ts frontend/src/types/types.test.ts
git commit -m "feat(types): native_confidence, stats distribution, instance config"
```

---

## Final foundation verification

- [ ] **Backend suite green:** `uv run --extra dev pytest -q` → all pass.
- [ ] **Frontend suite green:** `cd frontend && npm run test` → all pass.
- [ ] **Frontend builds:** `cd frontend && npm run build` → succeeds.
- [ ] **App boots in both themes:** `docker compose up -d --build` → api healthy; open the app, toggle dark/light, confirm brand palette + fonts render.

---

## Self-Review (completed against the resolved decisions)

1. **Spec coverage:** native-vs-decayed data (Tasks 1–4) ✓; dashboard distribution + errors (Task 5) ✓; read-only General config (Task 6) ✓; theme system + toggle (Tasks 8–9) ✓; missing primitives Slider/Popover/Tabs (Tasks 10–12) ✓; icons/charts/fonts (Task 7) ✓; logo recolor (Task 13) ✓; types (Task 14) ✓. Roles decision needs **no foundation work** (admin/user already exists) — handled in the Settings screen plan. The decay "half-life" caption fix is a copy change deferred to the Observable-Detail screen plan (data is made correct here).
2. **Placeholder scan:** none — every code step carries real code; the one runtime-dependent value (the `002` down_revision id) is called out with a verification step.
3. **Type consistency:** `native_confidence` is `int`/`number` end-to-end; stats keys (`confidence_distribution`, `feed_errors_24h`) match between Task 5 (backend) and Task 14 (types); `InstanceConfig` field names match Task 6's endpoint keys.

> **Open assumption to verify at execution time:** the public ingest entrypoint is referenced as `observable_service.ingest_raw_observables(db, feed, raws)`. Confirm the real exported function name/signature in `src/cti/services/observable_service.py` and adjust the three test call-sites if it differs.
