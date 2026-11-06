# EmergentCTI

Lightweight Cyber Threat Intelligence platform for IOC feed aggregation and export, with a web dashboard and user authentication.

## Quick Start

```bash
cp .env.example .env
```

Edit `.env` and set the required values (the stack will not start until these are set):

- `POSTGRES_PASSWORD` — database password
- `REDIS_PASSWORD` — Redis password
- `FEED_ENCRYPTION_KEY` — Fernet key used to encrypt stored feed credentials. Generate one with:
  ```bash
  python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
  ```
- `JWT_SECRET_KEY` — **required** when `ENVIRONMENT=production` (the default). The API refuses to start without it. Generate one with:
  ```bash
  python -c "import secrets; print(secrets.token_urlsafe(32))"
  ```
- `ADMIN_PASSWORD` — password for the initial `admin` user, created on first boot. Set it or you won't be able to log into the web UI.

Then start the stack:

```bash
docker compose up -d
```

**Web UI:** http://localhost:8080 — log in as `admin` with the `ADMIN_PASSWORD` you set.

**API key** (for programmatic access) is auto-generated on first boot. Grab it from the logs — it's shown only once:

```bash
docker compose logs api | grep -A1 "INITIAL API KEY"
```

## Features

- **Web Dashboard** — Aggregation health, 14-day ingestion trend, observable-type breakdown, feed status, and confidence distribution; dark/light themes with a toggle
- **User Authentication** — JWT session login for the web UI with `admin` / `user` roles; `X-API-Key` auth for programmatic access
- **Feed Aggregation** — Ingest from 12 pre-configured feeds (AbuseIPDB, abuse.ch, CINSscore, DShield, etc.) plus custom feeds
- **Blocklist Export** — Plain-text exports for direct firewall integration (pfSense, PAN EDLs, etc.) and full JSON export
- **Reversible Allowlist** — Typed exact values, IPv4/IPv6 CIDRs, and domain suffixes stay visible as allowlisted but are excluded from every export
- **Saved Export Profiles** — Shared text/JSON exports with type, confidence, freshness, and feed filters; preview and stable authenticated download URLs
- **Tags and TLP markings** — Flat tags on observables and reports; FIRST TLP 2.0 markings on feeds, reports and observables, enforced in every export (see [Tags and TLP](#tags-and-tlp))
- **Retention Enforcement** — Daily, bounded deletion of stale observables and their sources (180 days by default; `0` disables deletion)
- **Confidence Scoring** — Dual-mode scoring with native feed scores and linear time decay; native-vs-decayed surfaced per observable
- **Observable Types** — IP addresses, domains, URLs, file hashes, emails, command lines

## API

Endpoints authenticate with an `X-API-Key` header (programmatic access) **or** a JWT session cookie (web UI). `GET /api/v1/health` is public.

| Endpoint | Description |
|----------|-------------|
| `GET /api/v1/observables` | Search/filter observables |
| `GET /api/v1/observables/{id}` | Observable detail with per-source attribution |
| `GET /api/v1/feeds` | List feeds |
| `POST /api/v1/feeds/{id}/trigger` | Run a feed now (admin) |
| `GET /api/v1/export/blocklist/{type}` | Plain-text blocklist |
| `GET /api/v1/export/json` · `GET /api/v1/export/text` | JSON / plain-text export |
| `GET /api/v1/allowlist` | List allowlist policies; POST and DELETE /{id} require admin |
| `GET /api/v1/export/profiles` | Saved export profiles; POST, PUT and DELETE require admin |
| `GET /api/v1/export/profiles/{id}/preview` | Eligible count, allowlisted and TLP exclusion counts, and up to 20 sample values |
| `GET /api/v1/export/profiles/{id}/download` | Download with saved filters, current allowlist and TLP policy |
| `PUT /api/v1/observables/{id}/tlp-override` · `DELETE` | Reclassify an observable's TLP marking, reason required (admin) |
| `PUT /api/v1/observables/{id}/tags` · `PUT /api/v1/reports/{id}/tags` | Replace an item's tags (admin) |
| `GET /api/v1/tags` | Tags with usage counts; POST and DELETE /{id} require admin |
| `GET /api/v1/stats` | Dashboard stats |
| `GET /api/v1/settings/api-keys` · `/users` · `/config` | API keys, users, read-only config (admin) |

Configuration is read-only through the API: `GET /api/v1/settings/config` shows the current values, and there is no write route (`PUT` returns 405). To change a setting, edit `.env` and restart the stack.

## Safe exports and retention

Use **Settings → Allowlist** to protect known-good values without losing feed provenance. Exact entries are type-specific; CIDRs match IP indicators only; domain suffixes match the domain itself and subdomains at label boundaries (not URLs or email addresses). Domain matching is case-insensitive; other non-IP types match literally, including case and whitespace. Admins can also allowlist an exact value (or an IP range) from its observable detail page. A reason is required for every rule.

Allowlisting does **not** discard incoming indicators. Matching indicators remain searchable and marked in the UI, but all text, JSON, blocklist, and profile exports exclude them. Removing the final matching rule makes the indicator eligible again. Exports evaluate current allowlist policies on every request, including when blocklist candidates come from the cache. Text formats omit values containing control characters so one stored value cannot inject additional blocklist lines; JSON retains literal values.

Use **Settings → Export profiles** to save an export's filters, preview its contents, and copy its stable download URL. Profile downloads include all eligible values in either format; the ordinary JSON export keeps its explicit `limit` parameter. URLs still require a session cookie or `X-API-Key`; they are not public capability links. A feed referenced by a profile cannot be deleted until the profile is updated or removed. Example firewall-client request:

```bash
curl -H "X-API-Key: $CTI_API_KEY" \\
  "https://cti.example.com/api/v1/export/profiles/PROFILE_UUID/download"
```

Retention is **irreversible**, unlike allowlisting: a daily scheduled job removes indicators whose `last_seen` (or `created_at` when unknown) is strictly older than `OBSERVABLE_RETENTION_DAYS`. Manual and allowlisted indicators are also subject to retention. Allowlist rules and saved profiles themselves are retained. Set `OBSERVABLE_RETENTION_DAYS=0` and restart to disable deletion; negative values are rejected. The job runs at 03:00 UTC daily (a fixed schedule, not a 24-hour timer reset on each restart). Back up the database before enabling or shortening retention on existing deployments.

Existing installations must apply the new schema before running the updated API:

```bash
uv run alembic upgrade head
```

Research exports including allowlisted indicators, STIX/TAXII/MISP, and runtime policy configuration are not included in this slice (audit history is covered in [Audit history](#audit-history)).

## Tags and TLP

**Tags** are flat labels on observables and reports (no hierarchy, no
collections). Names are normalized: trimmed, whitespace runs become `-`, and
lowercased; 1–50 characters from `a-z 0-9 . _ : / -`. Admins assign tags; anyone
signed in can filter by them (`?tag=a&tag=b` matches any listed tag), including
on ad-hoc exports and in export profiles. A tag used by an export profile cannot
be deleted until the profile stops using it.

**TLP markings** follow FIRST TLP 2.0 and are a *sharing policy*. They are not
access control: everyone who can sign in can still see every observable,
report and marking in the app. Markings are set on feeds (admin; applies to
everything the feed contributes), on reports (the attachment inherits it), and
on manually created observables. An observable's effective marking is the
**most restrictive** of its inputs, computed on every read and export. An
Unspecified input lowers CLEAR/GREEN to Unspecified, because nobody said it was
shareable, but AMBER and above still win. Imports, feed runs and new report
links cannot loosen a marking. Only an admin can: by reclassifying the
observable (an override that needs a reason), or by loosening a feed's or
report's marking, which also needs a reason (`tlp_change_reason`) and is logged.

What each export destination allows:

| Effective marking | `internal` (ad-hoc exports, internal profiles) | `community` profiles | `public` profiles |
|---|---|---|---|
| Unspecified | yes | no | no |
| TLP:CLEAR | yes | yes | yes |
| TLP:GREEN | yes | yes | no |
| TLP:AMBER | yes | no | no |
| TLP:AMBER+STRICT | yes | no | no |
| TLP:RED | **never** | **never** | **never** |

- **Unspecified is internal-only.** It is exported to your own controls, never
  to community or public destinations.
- **TLP:RED never leaves the application** through any export, profile download
  or API key, including when a blocklist comes from the cache. For API-key
  callers RED observables and reports do not exist: lists leave them out,
  detail, attachment and edit endpoints return `404`, and reports drop linked
  RED observables. Report extraction previews RED matches as new values, and
  import skips them (`skipped`, reason `not_importable`) without changing them.
  An API key cannot change a RED feed's marking. Signed-in users still see and can open everything in the
  app; declassifying a RED item needs an interactive admin session. Every
  attachment response carries `X-TLP-Marking`.
- TLP and the allowlist are independent: a value is exported only if it passes
  both. Ad-hoc exports report withheld rows in `X-TLP-Excluded`, and a profile
  preview lists them per marking (`excluded_by_tlp`) before you change its
  destination.
- No feature sends instance data to an external AI provider today. Any future
  one must use the code-only `external_ai` gate, which allows CLEAR and GREEN.

**Rollout:** the migration leaves every marking Unspecified and every existing
export profile `internal`. Because `internal` allows Unspecified, **all existing
exports return exactly what they returned before** until an admin marks
something RED or switches a profile to `community` or `public`. Downgrading the
schema (`alembic downgrade 008`) removes markings and tags.

## Reports & attachments storage/backup

Reports and their attachments are stored in PostgreSQL, including the original
attachment bytes. Back up reports with the rest of the database using `pg_dump`;
there is no separate report-upload directory to copy. Attachments are limited to
20 MiB by default. Set `REPORT_MAX_UPLOAD_BYTES` to change the API limit and keep
the nginx `client_max_body_size` setting above that value.

## AI providers

Administrators can configure bring-your-own API keys for Anthropic, OpenAI,
OpenRouter, and xAI (Grok) under **Settings → AI**. Create keys in the provider
consoles: [Anthropic](https://console.anthropic.com/settings/keys),
[OpenAI](https://platform.openai.com/api-keys),
[OpenRouter](https://openrouter.ai/settings/keys), or
[xAI](https://console.x.ai/).

`FEED_ENCRYPTION_KEY` encrypts AI provider keys as well as feed credentials. Back
it up with the database: changing or losing it makes stored keys unreadable, and
each provider key must then be re-entered. Provider usage charges and data-handling
policies belong to the external provider. Saving a key, checking a connection, and
listing models do not send CTI instance data; only the separately confirmed
inference test makes a potentially billable request, using one fixed tiny prompt.

### AI usage guardrails

**Budgets are local estimates, not a billing guarantee.** EmergentCTI estimates
cost from prices an administrator enters and from the token counts a provider
reports. It cannot see your provider bill. Set hard spending limits in each
provider's console: those are the real safeguard.

- **In scope:** connection inference tests (`inference_test`). Report generation
  will be added when it exists. Model-list refreshes and credential checks are not
  inference and are never counted.
- **Period:** a UTC calendar month, `[YYYY-MM-01T00:00Z, next month)`. A request
  belongs to the month in which it started.
- **Policy** (Settings → AI, admin only; `GET`/`PUT /api/v1/settings/ai/usage-policy`):
  monthly budget (blank means none), max output tokens per request (sent to the
  provider as its max-tokens limit), concurrent requests, requests per minute
  (every attempt counts, failures included), and whether models with no pricing
  are blocked (the default) or permitted. Changes are audited as
  `ai_usage_policy.update`.
- **Pricing** (`/api/v1/settings/ai/pricing`) is admin-entered per provider and
  model, in USD per million input and output tokens. No price table ships. Changes
  are audited as `ai_pricing.update` and `ai_pricing.delete`.
- **Before sending**, the server reserves the most the request could cost:
  `(UTF-8 bytes of the prompt + 64) × input price + max output tokens × output price`.
  It rejects the request without contacting the provider if the model is unpriced
  and blocked (409), too many requests are in flight or were made in the last
  minute (429), or committed spend plus the reservation would exceed the budget
  (402). On PostgreSQL the check holds a row lock, so simultaneous requests and
  multiple workers cannot overrun the limits.
- **After the response**, the reservation is settled once: with the estimated cost
  when the provider reported both token counts and the model is priced. Otherwise
  the cost stays **unknown**, never zero, and the reservation keeps counting as
  committed spend whenever the request may have been billed (success, timeout, 429,
  5xx, cancellation). Requests the provider refused outright (400, 401, 403, 404,
  or never sent) count as zero. A reservation left behind by a crash is shown as
  stale. It stops counting toward concurrency after the request timeout plus 60
  seconds, but still counts as spend.
- Nothing is retried automatically and there is no fallback to another provider
  or model. A retry by the user is a new, separately counted request.
- Usage records (`GET /api/v1/settings/ai/usage` and `/usage/records`) hold
  metadata only: actor, action, provider, model, timestamps, status, token counts
  and estimates. They never hold prompts, responses, provider error text or keys.
  Unknown token counts and costs are shown as unknown, and totals report how many
  requests had unknown usage or cost, including refused requests (which still add
  nothing to committed spend). Reports cover UTC calendar months from `2000-01`
  to `9999-11`.

## Audit history

EmergentCTI keeps an admin-only history of sensitive changes and disclosures in the
`audit_events` table: allowlist, export-profile, report, tag/TLP, feed, API-key,
user, and AI-provider changes; export and attachment downloads; outbound
AI requests; and one aggregated event per scheduled retention run. Admin users read
it in **Settings → Audit** or at `GET /api/v1/audit/events`, filtered by time range,
actor, action, resource, and outcome. API keys cannot read it (403), so a leaked key
cannot inspect the trail of its own use; `GET /api/v1/audit/meta` lists the action catalog. There are
no routes to edit or delete events. Events for retired actions (such as `settings.update`, from the
removed `PUT /settings/config`) remain listable and filterable until retention removes them.

Each event records the UTC time, the actor (a user, an API key by its **record id**
and name, never the key itself, or a system job), the action, the resource with a
label snapshot, the outcome, and a small sanitized summary. Events have no foreign
keys, so deleting a user, key, report, or feed keeps its history. Summaries never
contain keys, passwords, authorization headers, report bodies, AI prompts or
responses, or provider error bodies; report edits record changed field names only.

**What a write failure means.** A successful change and its event commit in the same
transaction: if the event cannot be written, the change rolls back and the request
fails. Denied and failed attempts are recorded best-effort; if that write fails it is
logged and the response is unchanged. Downloads and AI requests fail closed: if the
`initiated` event cannot be written, the request returns `503 Audit log unavailable`
and nothing is disclosed. A download is then marked `completed` once the whole body
has been handed to the server, or `interrupted` if sending fails or the client
disconnects. `completed` does not prove the client received the file; an
`initiated` event without a `completed` one means delivery was not proven.

**Retention.** A daily job at 03:30 UTC deletes events older than
`AUDIT_RETENTION_DAYS` (default 365, allowed 30–3650; it cannot be disabled) in
batches of 5,000 and records one `audit.retention_cleanup` event. This is
independent of `OBSERVABLE_RETENTION_DAYS`; snapshot labels such as observable
values and report titles remain for the audit retention period even after the
underlying item is removed by observable retention.

**Storage and backup.** Expect roughly 0.5–1 KB per event. Most volume comes from
automated downloads: a firewall pulling a blocklist every 5 minutes adds about
105,000 events (roughly 50–100 MB) a year. Back up `audit_events` with the rest of the
database (`pg_dump` includes it).

**What is not claimed.** History is append-only *through the application*. A
database administrator can still change or delete rows; there is no cryptographic
integrity or external copy. SIEM forwarding and tamper-evident storage are possible
follow-ups. Requests rejected before reaching a handler (unauthenticated `401`s and
malformed request bodies) are not recorded.

## Development

Backend — run the API and tests with [uv](https://docs.astral.sh/uv/):

```bash
uv run --extra dev pytest
```

PostgreSQL-specific migration, row-lock, and foreign-key checks are opt-in (they create and drop a randomly named schema, not public tables):

```bash
CTI_TEST_POSTGRES_URL='postgresql+psycopg_async://USER:PASSWORD@HOST/TEST_DB' \\
  uv run --extra dev pytest tests/test_postgres_policies.py
```

Use a test database account with `CREATE SCHEMA` permission. Without this variable, those checks are skipped; the ordinary suite runs on SQLite.

Frontend — the web UI lives in `frontend/`:

```bash
cd frontend
npm install
npm run dev      # Vite dev server on :5173 (proxies /api to the backend)
npm run test     # Vitest
```
