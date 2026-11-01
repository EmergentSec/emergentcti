# Analyst confidence: floor and pinned override (issue #28) — shared contract

Backend and frontend are built in parallel against this contract. Neither side
changes it unilaterally; raise a question to the coordinator instead.

## Problem

Feed ingest and decay recompute `observables.confidence_score` as
`MAX(observable_sources.source_confidence)`. They ignore analyst decisions, so
a low-scoring feed can silently lower an observable an analyst created
manually or imported from a report (#14). The observable can then drop out of
blocklist exports.

## Rule (decided in #28)

```
effective =
  confidence_override                                   if an override is set
  else GREATEST(max feed source_confidence,
                manual_confidence,
                max report_observables.analyst_confidence)  if any of these exist
  else the current confidence_score (unchanged)
```

- **Floor (default):** analyst decisions and feeds combine by MAX. A feed can
  raise an analyst-set confidence but never lower it.
- **Pinned override:** an admin can set an exact value from 0 to 100, which
  may be below the feeds (for example, to demote a false positive). While it
  is set, feed runs, decay, manual re-creates and report imports **never**
  change `confidence_score`. Clearing it recomputes with the floor rule.
- Feed-only observables (no analyst decisions, no override) score exactly as
  before.

## Data model (migration `008`)

`observables` gains these nullable columns:

| column | type | notes |
|---|---|---|
| manual_confidence | integer null, CHECK 0–100 when not null | highest confidence given via manual create (`POST /observables`) |
| confidence_override | integer null, CHECK 0–100 when not null | pinned override |
| override_set_at | timestamp null | |
| override_set_by_id | uuid null, FK users.id ON DELETE SET NULL | |

CHECK constraint: `override_set_at` is null whenever `confidence_override` is
null.

Backfill in the migration: for observables with **no** `observable_sources`
rows (created manually before this change), set
`manual_confidence = confidence_score`. Must work on SQLite and PostgreSQL;
use `batch_alter_table` like `007`.

## Backend

One function owns the rule:
`services/confidence.py: recompute_effective_confidence(db, observable_ids)`.
It is a single set-based UPDATE using `func.greatest` (the test suite
registers a NULL-ignoring `greatest` for SQLite) and `coalesce`, and it
respects the override. Every recompute site calls it:

| Site | Today | Change |
|---|---|---|
| `observable_service.bulk_upsert_from_feed` step 3 | `coalesce(max(source),50)` | use the shared recompute |
| `confidence.apply_confidence_decay` | MAX of sources | use the shared recompute |
| `observable_service.create_observable` (manual) | `confidence = greatest(existing, provided)` | upsert `manual_confidence = greatest(existing, provided)`, then recompute (the override still wins) |
| report import (`report_import_service.import_candidates`) | new: confidence = chosen; existing: untouched | after the link rows are written, recompute all imported ids. A higher analyst confidence now **raises** an existing observable unless it's overridden. This supersedes the #14 rule "existing observables keep their confidence" (#14's contract doc gets a note). |
| unlink report observable, delete report | no recompute | recompute affected observables after commit, since an analyst floor may have gone |

Every site that changes confidence calls `invalidate_observable_caches()` after
commit (`core/redis.py`). This includes report imports where `created == 0`
but an existing observable's confidence was raised.

### API

| Method | Path | Auth | Body | Response |
|---|---|---|---|---|
| PUT | `/observables/{id}/confidence-override` | admin | `{ "confidence": int 0–100 }` | 200 `ObservableResponse`; 404; 422 |
| DELETE | `/observables/{id}/confidence-override` | admin | | 200 `ObservableResponse` (recomputed by the floor rule); 404 unknown observable; idempotent when no override is set |

`ObservableResponse` (and every list/detail payload that uses it) gains:

```ts
manual_confidence: number | null;
confidence_override: {
  value: number;
  set_at: string;                 // ISO timestamp
  set_by: string | null;          // username; null if set via an API key or the user was deleted
} | null;
```

The export JSON format is unchanged.

## Frontend

On the observable detail page (`ObservableDetailPage.tsx`):

- **Confidence display:** when an override is active, show a badge ("Pinned by
  <user>, <relative time>") next to the confidence. When `set_by` is null,
  show "Pinned by an API key or removed user, <time>". The page also shows
  `manual_confidence` labelled "Manual floor" when it is non-null. It is not
  the whole analyst floor, because report-import confidences also count.
- **Admin-only "Override confidence" control:**
  - Number input, 0–100, whole numbers only, prefilled with the current
    effective confidence.
  - Help text: "Pins this observable's confidence. Feed updates and decay
    won't change it until you clear the override. Lower values can remove it
    from blocklist exports."
  - Buttons "Set override" and, when one is active, "Clear override". Clearing
    asks for confirmation and explains that confidence will be recomputed
    from feeds and analyst decisions.
- **Non-admins** see the badge but no controls.
- **After set or clear:** invalidate `['observable', id]`, `['observables']`
  and `['dashboard']`, and show a toast. On 422, show the server `detail`.
- **Observables list page:** optional small "pinned" marker in the confidence
  column. Nice to have, not required.
