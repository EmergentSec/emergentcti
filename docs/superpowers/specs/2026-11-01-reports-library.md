# Reports library (issue #12) — shared contract

Backend and frontend are built in parallel against this contract. Neither side
changes it unilaterally; raise a question to the coordinator instead.

Scope guardrail: this is a report *library*, not a document-intelligence platform.
No PDF text extraction/OCR, no URL fetching, no IOC auto-extraction, no AI calls,
no per-report sharing/TLP. Must work with no AI provider configured.

## Storage decision

Attachments are stored **in PostgreSQL** (`report_attachments.content`, `LargeBinary`
/ `bytea`), not on the filesystem.

- Survives container restarts via the existing `postgres_data` volume.
- Backup = the existing `pg_dump` of the database (document this in README).
- No filesystem paths exist, so path traversal is impossible by construction; the
  storage identifier is the server-generated attachment UUID.
- Deleting a report cascades to its attachment row (ORM cascade + `ON DELETE CASCADE`).
- `content` must be `deferred()` / never loaded by list or detail queries; only the
  download endpoint reads it.

One attachment per report in the MVP (replace = upload again).

## Data model (migration `005`)

`reports`
| column | type | notes |
|---|---|---|
| id | uuid pk | |
| title | varchar(500) not null | |
| origin | varchar(16) not null | `provider` \| `internal` (CHECK constraint) |
| source_name | varchar(255) null | provider name (origin=provider) or author (origin=internal) |
| published_at | timestamp null | publication date when known |
| summary | text null | |
| source_url | varchar(2048) null | metadata only, never fetched; must be `http(s)://` |
| content | text null | pasted Markdown / plain text |
| content_format | varchar(16) not null default `markdown` | `markdown` \| `text` (CHECK) |
| is_ai_generated | bool not null default false | |
| ai_provider | varchar(255) null | null = unknown |
| ai_model | varchar(255) null | null = unknown |
| ai_generated_at | timestamp null | null = unknown |
| created_by_id | uuid null fk users.id ON DELETE SET NULL | |
| created_at / updated_at | timestamp | TimestampMixin |

Indexes: `published_at`, `origin`, `source_name`, `created_at`.
Validation: `ai_*` fields must be null when `is_ai_generated` is false (422 otherwise).

`report_attachments`
| column | type | notes |
|---|---|---|
| id | uuid pk | server-generated storage id |
| report_id | uuid fk reports.id ON DELETE CASCADE, UNIQUE | |
| original_filename | varchar(255) not null | display only; basename, control chars stripped |
| content_type | varchar(100) not null | server-decided from allowlist, never client-trusted |
| size_bytes | bigint not null | |
| sha256 | char(64) not null | |
| content | bytea not null | deferred |
| created_at | timestamp | |

`report_observables` (link table)
| column | type | notes |
|---|---|---|
| report_id | uuid fk reports.id ON DELETE CASCADE | pk part |
| observable_id | uuid fk observables.id ON DELETE CASCADE | pk part |
| created_at | timestamp | |

Retention (`services/retention.py`) must explicitly delete `report_observables`
rows for expired observables before deleting the observables (SQLite tests do not
enforce FKs) and must never delete reports or attachments. Linking never changes
observable confidence, allowlist, sources, or export eligibility.

## Upload rules

- Allowed: `.pdf` → `application/pdf`; `.md` / `.markdown` → `text/markdown`;
  `.txt` → `text/plain`. Decide by extension **and** content:
  PDF must start with `%PDF-`; text types must decode as UTF-8 and contain no NUL bytes.
- Size limit `REPORT_MAX_UPLOAD_BYTES` setting, default 20 MiB. Read in chunks and stop
  at limit+1 → **413**. Empty file → 422. Unsupported type/sniff mismatch → **415**.
- `frontend/nginx/default.conf`: `client_max_body_size 21m;` on `/api/`.
- Requires `python-multipart` dependency.

## API (`/api/v1/reports`, all JSON unless stated)

Auth: every endpoint requires `get_current_auth`; mutating endpoints require
`require_admin`. Anonymous → 401, analyst on write → 403.

| method | path | auth | body / query | response |
|---|---|---|---|---|
| GET | `/reports` | user | `q` (title/summary, case-insensitive contains), `origin`, `source_name` (exact), `published_from`, `published_to` (ISO dates, inclusive), `ai_generated` (bool), `page`≥1, `size` 1–100 default 25 | `ReportListResponse` |
| GET | `/reports/sources` | user | | `string[]` distinct non-null `source_name`, sorted |
| POST | `/reports` | admin | `ReportCreate` | 201 `ReportDetail` |
| GET | `/reports/{id}` | user | | `ReportDetail` / 404 |
| PATCH | `/reports/{id}` | admin | `ReportUpdate` (partial) | `ReportDetail` |
| DELETE | `/reports/{id}` | admin | | 204 (cascades attachment + links) |
| PUT | `/reports/{id}/attachment` | admin | multipart field `file` | `ReportAttachment` (replaces existing) |
| DELETE | `/reports/{id}/attachment` | admin | | 204 / 404 if none |
| GET | `/reports/{id}/attachment` | user | | file bytes / 404 if report or attachment missing |
| POST | `/reports/{id}/observables` | admin | `{ "observable_id": uuid }` | 201 `LinkedObservable`; 404 unknown observable; idempotent if already linked (200) |
| DELETE | `/reports/{id}/observables/{observable_id}` | admin | | 204 / 404 |
| GET | `/observables/{id}/reports` | user | | `ReportSummary[]` (newest first); 404 if observable missing |

List ordering: `published_at desc nulls last, created_at desc`.

Download headers: `Content-Type` = stored allowlisted type, `Content-Disposition:
attachment; filename*=UTF-8''<rfc5987-encoded original_filename>`,
`X-Content-Type-Options: nosniff`, `Content-Security-Policy: sandbox; default-src 'none'`,
`Cache-Control: private, no-store`.

### Schemas

```ts
type ReportOrigin = 'provider' | 'internal'
type ContentFormat = 'markdown' | 'text'

interface ReportAttachment {
  id: string; original_filename: string; content_type: string;
  size_bytes: number; sha256: string; created_at: string;
}
interface ReportSummary {
  id: string; title: string; origin: ReportOrigin; source_name: string | null;
  published_at: string | null; summary: string | null;
  is_ai_generated: boolean; ai_provider: string | null; ai_model: string | null;
  has_attachment: boolean; created_at: string; updated_at: string;
}
interface LinkedObservable { id: string; type: string; value: string; confidence_score: number }
interface ReportDetail extends ReportSummary {
  source_url: string | null; content: string | null; content_format: ContentFormat;
  ai_generated_at: string | null; created_by: string | null /* username */;
  attachment: ReportAttachment | null;
  observables: LinkedObservable[];   // stale/removed observables simply absent
}
interface ReportListResponse { items: ReportSummary[]; total: number; page: number; size: number; pages: number }
interface ReportCreate {
  title: string /* 1–500, trimmed */; origin: ReportOrigin; source_name?: string | null;
  published_at?: string | null; summary?: string | null; source_url?: string | null;
  content?: string | null /* ≤ 1,000,000 chars */; content_format?: ContentFormat;
  is_ai_generated?: boolean; ai_provider?: string | null; ai_model?: string | null;
  ai_generated_at?: string | null;
}
type ReportUpdate = Partial<ReportCreate>
```

## Frontend

- Nav item **Reports** (`/reports`, Phosphor `FileText` icon) between Observables and Feeds;
  `PAGE_META` entry; routes `reports`, `reports/:id`.
- List page: search box (title/summary), filters (origin, source from `/reports/sources`,
  published date range, AI-generated), paginated table using existing `Pagination`,
  AI badge, attachment indicator. Admin-only "New report" button.
- Detail page: metadata panel, AI provenance block (shows "Unknown" for null fields),
  source URL as plain external link with `rel="noopener noreferrer nofollow"` and only
  when `http(s)`, rendered content, attachment download button, linked observables list
  (links to `/observables/:id`), admin edit/delete (confirm Dialog) / upload / link /
  unlink controls.
- Content rendering: `markdown` via `react-markdown` **without** `rehype-raw` (raw HTML is
  shown as text, never executed), `skipHtml`, links forced to `target=_blank rel=noopener
  noreferrer nofollow`, images not rendered (show alt text/link). `text` in a `<pre>`
  with wrapping. Never `dangerouslySetInnerHTML`.
- Download goes through the authenticated axios client (`responseType: 'blob'`) and an
  object URL, so the cookie auth/refresh flow applies.
- Observable detail page gets a "Reports" section listing `/observables/{id}/reports`.
- Reuse existing UI primitives (`components/ui/*`), design tokens, light/dark support.
