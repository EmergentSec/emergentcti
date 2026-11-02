# Audit history (issue #16): contract

Status: binding contract for every worker on #16. If code and this document
disagree, raise it with the coordinator; do not silently diverge.

## Goal and boundaries

An attributable, admin-only history of sensitive changes and disclosures.
It is not case management: no tickets, timelines, assignments, or
investigation workflow. It does not copy report bodies, credentials, prompts,
or provider responses into a second store. SIEM forwarding and cryptographic
integrity are follow-ups. The history is append-only *through the application*;
we do not claim tamper-proofing against a database administrator.

## Data model: `audit_events` (migration `010_add_audit_events.py`)

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `occurred_at` | timestamptz, not null | UTC, set by the server |
| `actor_type` | enum `user` / `api_key` / `system` | |
| `actor_id` | string(64), nullable | user UUID, API-key **record** UUID, or job id such as `system:observable_retention`. Never a raw key. |
| `actor_label` | string(255), nullable | snapshot: username, API-key name, or job name |
| `action` | string(64), not null | catalog below |
| `resource_type` | string(32), not null | e.g. `report`, `feed`, `export` |
| `resource_id` | string(64), nullable | UUID or other stable id |
| `resource_label` | string(255), nullable | snapshot (report title, feed name, profile name) so history survives deletion |
| `outcome` | enum `succeeded` / `failed` / `denied` / `initiated` / `completed` / `interrupted` | |
| `summary` | JSON, not null, default `{}` | sanitized; at most 4 KB serialized |

No foreign keys: deleting a user, key, report, or feed must not delete or
null out history. Indexes: `occurred_at`, `(actor_type, actor_id)`, `action`,
`(resource_type, resource_id)`, `outcome`. The model must work on SQLite (tests)
and PostgreSQL.

## Core API: `src/cti/services/audit.py`

```python
class ActorType(StrEnum): USER, API_KEY, SYSTEM
class AuditOutcome(StrEnum): SUCCEEDED, FAILED, DENIED, INITIATED, COMPLETED, INTERRUPTED

@dataclass(frozen=True)
class Actor:
    type: ActorType
    id: str | None
    label: str | None

def actor_from_auth(auth: AuthSubject) -> Actor        # User -> username; ApiKey -> key.id/key.name
def system_actor(job_id: str, label: str) -> Actor

def record(db, *, actor, action, resource_type, resource_id=None,
           resource_label=None, outcome=AuditOutcome.SUCCEEDED, summary=None) -> AuditEvent
    # Adds the event to the caller's session. No flush, no commit.

async def record_independent(*, actor, action, resource_type, resource_id=None,
           resource_label=None, outcome, summary=None, strict: bool) -> uuid.UUID | None
    # Own session and commit. strict=True raises AuditWriteError on failure;
    # strict=False logs at ERROR (no summary contents in the log) and returns None.

def sanitize_summary(summary: Mapping | None) -> dict

class AuditWriteError(Exception)

def audited_admin(action: str, resource_type: str) -> Depends-able
    # Same as require_admin, but a non-admin user gets a `denied` event
    # (record_independent, strict=False) before the 403.

class AuditedDownload(Response)   # see "Disclosures" below
```

Use the existing session factory (`cti.core.database.async_session_factory`)
for independent writes, through one module-level indirection that tests can
point at the test engine.

Approved additive helpers (the preferred path for instrumenting routers; see
the module docstring for usage examples):

```python
async def begin_disclosure(*, actor, action, resource_type, resource_id=None,
           resource_label=None, summary=None) -> Disclosure
    # record_independent(outcome=INITIATED, strict=True); on AuditWriteError
    # raises HTTPException(503, "Audit log unavailable"). Call before any body exists.

@dataclass(frozen=True)
class Disclosure:   # event_id, actor, action, resource_type, resource_id, resource_label
    async def record_outcome(self, outcome, summary=None) -> uuid.UUID | None
    # Non-strict; adds {"initiated_event_id": str(event_id)} to the summary.

AuditedDownload(content, *, disclosure, status_code=200, headers=None,
                media_type=None, chunk_size=65536)

audited_admin(action, resource_type, *, resource_id_param=None)
    # resource_id_param names a path parameter used as the denied event's resource_id.
```

`ACTION_CATALOG` (action → resource_type) in `services/audit.py` is the single
source of truth; `record`/`record_independent` raise `ValueError` for an
action not in it or a mismatched `resource_type`.

## Write semantics

These are the rules that satisfy "never falsely report an event was recorded".

1. **Successful mutations** call `record(db, ...)` in the same session and
   transaction, before the route's `await db.commit()`. The event commits with
   the change or not at all. A failed audit insert fails the commit, so the
   mutation rolls back and the client gets a 5xx. A success event can never
   exist for a change that rolled back.
2. **Failed and denied attempts** on covered actions (403 from a non-admin,
   404 not found, 409 conflict, 422 service-level validation, provider errors)
   use `record_independent(..., strict=False)` because the request transaction
   rolls back. Summary carries `{"reason": "<short code>", "status": <http
   status>}`. If this write fails it is logged; the response the client would
   have got is unchanged. These events never use `succeeded`. Pydantic body
   validation that FastAPI rejects before the handler runs is not audited.
   Unauthenticated (401) requests are not audited: there is no actor.
   **On a failure path, build the actor with `actor_from_auth(auth)` first,
   then `await db.rollback()`, then call `record_independent`.** PostgreSQL
   rejects statements in an aborted transaction (for example after an
   `IntegrityError`), and SQLite (tests) allows one writer, so an open
   request write would block the independent insert. In tests, independent
   writes run in a SAVEPOINT on the shared test session's connection
   (`tests/conftest.py`); the `separate_audit_sessions` fixture gives each
   write its own connection to prove independence.
3. **Disclosures** (export downloads, report attachment downloads, outbound AI
   requests) fail closed: before any content leaves, write an `initiated` event
   with `record_independent(..., strict=True)`. If that write fails, return
   `503 {"detail": "Audit log unavailable"}` and disclose nothing.
4. **Delivery outcome.** Download bodies are sent through `AuditedDownload`,
   which, once the ASGI send of the final body chunk returns, writes
   `completed`; if sending raises or the client disconnects (including
   `asyncio.CancelledError`), writes `interrupted` and re-raises. Both carry
   `{"initiated_event_id": ..., "bytes_sent": n}` and use `strict=False`.
   `completed` means the full body was handed to the server transport. It does
   not prove client receipt. An `initiated` event with no matching `completed`
   means delivery was not proven.
5. **AI requests** (provider check, model listing, inference test): `initiated`
   (strict) before calling the provider, then `succeeded` or `failed`
   (`strict=False`) with `{"operation", "provider", "model", "error_code"}`.
   Never store the prompt, response text, or provider error body.
6. **System jobs** write one aggregated event per run in their own session:
   - observable retention: `retention.observables_cleanup`, summary
     `{"deleted": n, "retention_days": d}`, outcome `succeeded`/`failed`;
   - audit retention: `audit.retention_cleanup`, `{"deleted": n, "cutoff": iso}`.
   Never one event per removed row.

## Sanitization (defense in depth)

Callers pass an explicit, minimal summary; `sanitize_summary` also enforces:

- Drop keys (case-insensitive, any depth) containing: `key`, `secret`,
  `token`, `password`, `passwd`, `authorization`, `auth_header`, `cookie`,
  `credential`, `prompt`, `response`, `content`, `body`, `headers`, `raw`.
  Exception: the exact key `api_key_id`.
- Strings truncated to 256 characters; lists truncated to 50 items with a
  `"…+N more"` marker; nesting deeper than 3 levels dropped.
- If the serialized result exceeds 4 KB, replace it with
  `{"truncated": true, "fields": [<top-level key names>]}`.
- Report edits record changed **field names** only (`{"changed_fields": [...]}`)
  plus TLP before/after when TLP changed. Never title/body text other than the
  `resource_label` snapshot.

## Action catalog

| Action | resource_type | Route(s) / source |
|---|---|---|
| `allowlist.create` / `allowlist.delete` | `allowlist_entry` | `/allowlist` |
| `export_profile.create` / `.update` / `.delete` | `export_profile` | `/export/profiles` |
| `export.download` | `export` (resource_id = profile id, or `json` / `text` / `blocklist:<type>`) | `/export/json`, `/export/text`, `/export/blocklist/{type}`, `/export/profiles/{id}/download` |
| `report.create` / `.update` / `.delete` | `report` | `/reports` |
| `report.tags_update` | `report` | `PUT /reports/{id}/tags` |
| `report.attachment_upload` / `.attachment_delete` | `report` | `/reports/{id}/attachment` |
| `report.attachment_download` | `report` | `GET /reports/{id}/attachment` |
| `report.observable_link` / `.observable_unlink` / `.import` | `report` | `/reports/{id}/observables`, `/reports/{id}/import` |
| `observable.tlp_override_set` / `.tlp_override_clear` | `observable` | `/observables/{id}/tlp-override` |
| `observable.tags_update` | `observable` | `PUT /observables/{id}/tags` |
| `tag.create` / `tag.delete` | `tag` | `/tags` |
| `feed.create` / `.update` / `.delete` / `.trigger` | `feed` | `/feeds` (summary: changed field names; never credentials or auth config values) |
| `api_key.create` / `api_key.revoke` | `api_key` | `/settings/api-keys` (resource_id = key record id) |
| `user.create` / `.update` / `.delete` / `.password_change` | `user` | `/settings/users` (role/active changes as before/after; never the password) |
| `settings.update` | `settings` | `PUT /settings/config` |
| `ai_provider.key_save` / `ai_provider.delete` | `ai_provider` | `/settings/ai/providers/{p}` (never the key) |
| `ai_default.set` / `ai_default.clear` | `ai_default` | `/settings/ai/default` |
| `ai.request` | `ai_provider` | check / models / inference-test |
| `retention.observables_cleanup` | `retention` | scheduler |
| `audit.retention_cleanup` | `audit` | scheduler |

`GET /api/v1/audit/meta` exposes this catalog so the UI need not hard-code it.

## History API (admin only)

`GET /api/v1/audit/events`. Requires `require_admin` (admin users and API keys,
matching the rest of the admin API). A non-admin user gets 403.

Query params, all optional and combinable: `since`, `until` (ISO 8601
datetimes, inclusive/exclusive), `actor_type`, `actor_id`, `action`
(repeatable; exact match), `resource_type`, `resource_id`, `outcome`
(repeatable), `page` (≥1, default 1), `size` (1–100, default 50).
Order is `occurred_at DESC, id DESC`.

```json
{"items": [{"id": "…", "occurred_at": "2026-11-02T10:00:00Z",
  "actor_type": "user", "actor_id": "…", "actor_label": "admin",
  "action": "report.update", "resource_type": "report", "resource_id": "…",
  "resource_label": "APT notes", "outcome": "succeeded",
  "summary": {"changed_fields": ["title"]}}],
 "total": 1, "page": 1, "size": 50, "pages": 1}
```

`GET /api/v1/audit/meta` returns
`{"actions": [...], "actor_types": [...], "outcomes": [...], "resource_types": [...], "retention_days": 365}`.

No POST, PUT, PATCH, or DELETE routes exist for audit events (405).

## Retention

`AUDIT_RETENTION_DAYS`: default 365, bounded `30 ≤ n ≤ 3650`, independent of
`OBSERVABLE_RETENTION_DAYS`. It cannot be disabled. A daily scheduler job
(`system:audit_retention`, 03:30 UTC) deletes events older than the cutoff in
bounded batches (5 000 rows, commit per batch) and writes one
`audit.retention_cleanup` event. README documents storage (roughly 0.5–1 KB
per row; a firewall polling a blocklist every 5 minutes adds about 105k rows
a year) and that backups must include `audit_events`.

## Frontend

Settings gains an **Audit** tab, visible to admins only. It shows a paginated
table (time, actor, action, resource, outcome) with filters for date range,
actor type plus actor id, action, resource type plus id, and outcome. Selecting
a row shows its summary as text key/value pairs, never as HTML. It uses the
existing `Pagination`, `Table`, `Select`, `Input` and `Badge` components, and
the API module `frontend/src/api/audit.ts` and hook `frontend/src/hooks/useAudit.ts`.

## Test obligations

Redaction; actor and resource deletion keep history; pagination and every
filter; non-admin 403 on read; no mutation routes; retention batches and the
bound; `completed` / `interrupted` / initiated-write-failure (503, no body)
streaming outcomes; mutation rollback produces no success event; audit insert
failure rolls back the mutation; a denied or failed attempt is never recorded as
`succeeded`; API-key attribution uses the record id and never the raw key.
Every covered action needs at least one success and one failure or denied test.
