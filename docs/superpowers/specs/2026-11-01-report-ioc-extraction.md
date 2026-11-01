# Report IOC extraction and reviewed import (issue #14) — shared contract

Backend and frontend are built in parallel against this contract. Neither side
changes it unilaterally; raise a question to the coordinator instead.

Builds on the Reports library (#12, `2026-11-01-reports-library.md`).

Scope guardrail: deterministic extraction plus an analyst-reviewed import. No
cases, assignments, investigation workflow, automatic blocking, AI calls, OCR,
or network access. Extraction is read-only: it never writes to the database.

## Safety invariants (both sides)

- No extracted URL, domain, or IP is ever fetched, resolved, or rendered as a
  clickable link. The frontend renders every extracted string as plain text
  (no Markdown, no `href`, no `dangerouslySetInnerHTML`).
- Document text is data. Nothing in it is interpreted as instructions,
  templates, or code.
- Extraction never mutates the observable database, report links, allowlist, or
  feeds. Only the import endpoint writes, and only for admins.
- Import accepts only candidates that the server itself re-extracts from the
  report at import time and finds valid. A client cannot import arbitrary
  values through this endpoint.
- The allowlist and export-time line-safety checks are unchanged. Imported
  observables are subject to them like any other observable.
- TLP: reports have no TLP or sharing fields (#12). There is nothing to enforce
  today. If report TLP is added later, the import must respect it.

## Document sources

Extraction reads, in order:

1. `report.content` (Markdown or plain text), when non-empty.
2. The attachment, when its `content_type` is `text/markdown` or `text/plain`
   (decoded as UTF-8; it was validated on upload).

A PDF attachment is reported as `unsupported` with reason
`pdf_text_extraction_unavailable`. No PDF library is added in this issue;
text-based PDF support and OCR are follow-ups. Any other attachment type is
reported as `unsupported` with reason `unsupported_content_type`.

If no source yields text, the preview has zero candidates and lists the
sources with their statuses. That is a 200, not an error.

Limits: at most 2,000,000 characters of combined text are scanned (the excess
is ignored and `truncated: true` is set). At most 1,000 unique candidates are
returned (also sets `truncated: true`). All patterns must run in linear time;
no nested unbounded quantifiers.

## Extraction rules

Supported types (`ObservableType` values): `ip-addr`, `domain-name`, `url`,
`file-hash`, `email-addr`. `command-line` is never extracted.

Refanging (applied to a matched token before normalization; record
`defanged: true` when any rule fired):
- `[.]`, `(.)`, `{.}`, `[dot]`, `(dot)`, `{dot}`, ` dot ` inside a host token → `.`
- `hxxp`, `hXXp`, `hxxps`, `hXXps` (case-insensitive) → `http` / `https`
- `[:]` → `:`, `[://]` / `[:]//` → `://`
- `[@]`, `[at]`, `(at)` → `@`

Normalization and validation:
- `ip-addr`: IPv4 and IPv6 via Python `ipaddress`; value is the canonical
  string form. Invalid octets (such as `999.1.1.1`) yield an `invalid`
  candidate. Private, loopback, link-local, multicast, reserved, or
  unspecified addresses are valid but carry the warning `non_public_ip`.
- `domain-name`: lowercase, trailing dot stripped, IDNA-encodable, at least
  two labels, labels of 1–63 chars of `[a-z0-9-]` not starting or ending with
  `-`, alphabetic TLD of at least 2 chars (or an `xn--` TLD). A bare token
  without defanging whose TLD is a common file extension (`exe dll pdf doc docx
  xls xlsx zip rar js ps1 bat sh py txt log png jpg gif`) is not emitted at all,
  to avoid `invoice.pdf` noise. If it was defanged (the author meant it), it is
  emitted with the warning `looks_like_filename`.
- `url`: scheme must be `http`, `https`, `ftp`, or `sftp` after refanging. The
  scheme and host are lowercased, the host is validated as a domain or IP, and
  the path, query, and fragment are kept as written. Trailing sentence
  punctuation `.,;:!?)]}>'"` is stripped. Not emitted when the host is invalid.
  Domains and IPs inside a URL are **not** emitted as separate candidates.
- `file-hash`: hex strings of exactly 32, 40, or 64 chars bounded by non-hex
  characters, lowercased. Warning `hash_md5` or `hash_sha1` for the 32- and
  40-char forms (weak but supported). A run of one repeated character
  (`0000…`) is `invalid`.
- `email-addr`: `local@domain` with a valid domain per the rules above; the
  domain part is lowercased and the local part is kept as written. The domain
  of an email is not emitted separately.

Unicode handling (pinned after backend review):
- Before matching, remove Unicode format characters (category `Cf`, for
  example U+200B–U+200D, U+202A–U+202E, U+2060–U+2064, U+FEFF) from the
  scanned text. Authors often use them to obfuscate indicators. `original`
  shows the text with them removed; `context` already strips them.
- A host run (domain, URL host, or email domain) must never start or end next
  to a non-ASCII letter or digit. When it would, extend the run over the
  adjacent non-ASCII label characters and IDNA-encode the whole host with
  Python's built-in `idna` codec (no new dependency), so
  `münchen.example` → `xn--mnchen-3ya.example`. If encoding fails, emit
  nothing for that run. Never emit a suffix of a longer host (no
  `nchen.example`).

Dedup: candidates are unique by `(type, value)` after normalization. The first
occurrence supplies `original` and `context`; `occurrences` counts all of them.

`context`: the surrounding text of the first occurrence, about 60 chars on each
side, with whitespace collapsed and a 200-char cap. Plain text only.

Status per candidate:
- `invalid`: failed validation. Never importable. `warnings` gives the reason
  (`invalid_ip`, `invalid_hash`, …).
- `existing`: an observable with the same `(type, value)` exists.
  `existing_observable_id` is set.
- `new`: valid, and no matching observable exists.

Additional flags:
- `already_attributed`: an `existing` observable is already linked to this
  report (by import or by a manual link).
- `allowlisted`: matches the current allowlist (via `allowlist_service`).
  `allowlist_matches` lists the matching entry values. It is still importable,
  but the UI deselects it by default; exports keep suppressing it.

## Attribution representation (migration `007`)

Report attribution lives on the existing `report_observables` link table, not
on `observable_sources`, so report provenance is never shown as a feed. Add
nullable columns:

| column | type | notes |
|---|---|---|
| imported_at | timestamp null | set on first import; null for manual links |
| imported_by_id | uuid null fk users.id ON DELETE SET NULL | |
| analyst_confidence | integer null, CHECK 0–100 when not null | the confidence the analyst chose |
| source_excerpt | varchar(500) null | `context` of the candidate at import |

The provider is the report itself (`report.origin`, `report.source_name`,
`report.source_url`); the link row points back to `report_id`. Manual links
from #12 keep these columns null.

Retention must still delete `report_observables` rows for expired observables
(unchanged behavior). Unlinking a report observable deletes the attribution row
and never deletes the observable.

## Confidence semantics

- The analyst chooses one confidence per import request: `confidence`,
  integer 0–100, **required** in the request. The UI default is **50**,
  documented in the UI next to the input. It is never inferred from the text.
- New observable: created with `confidence_score = confidence`,
  `first_seen = last_seen = now`, and **no** `observable_sources` row.
- Existing observable: `confidence_score`, `first_seen`, `last_seen`, and its
  `observable_sources` are **not modified**. Only attribution is added.
- `analyst_confidence` is recorded on the link row either way, for audit.
- Like manually created observables, a report-only observable's
  `confidence_score` follows the existing feed rules if a feed later reports
  the same value. This is documented, not changed.

## Idempotency

Import is idempotent per `(report_id, type, value)`:
- The observable upsert uses the `(type, value)` unique key, so it never makes
  a duplicate observable.
- Link upsert: if no link row exists, insert one with attribution. If a manual
  link row exists with null `imported_at`, fill in the attribution columns.
  If an imported row exists, leave it untouched (count as
  `already_attributed`).
- The whole import runs in one transaction; any error rolls back everything.

## API (all under `/api/v1`, admin-only via `require_admin`; anonymous → 401, analyst → 403)

| Method | Path | Body | Response |
|---|---|---|---|
| POST | `/reports/{id}/extract` | none | 200 `ExtractionPreview`; 404 unknown report. Performs no writes. |
| POST | `/reports/{id}/import` | `ImportRequest` | 200 `ImportResult`; 404 unknown report; 422 validation (see below) |

```ts
type CandidateStatus = 'new' | 'existing' | 'invalid';
type SourceStatus = 'extracted' | 'empty' | 'unsupported';

interface ExtractionSource {
  kind: 'content' | 'attachment';
  filename: string | null;          // attachment only
  content_type: string | null;      // attachment only
  status: SourceStatus;
  reason: string | null;            // e.g. 'pdf_text_extraction_unavailable'
}

interface ExtractionCandidate {
  type: 'ip-addr' | 'domain-name' | 'url' | 'file-hash' | 'email-addr';
  value: string;                    // normalized; for invalid ones, the refanged text
  original: string;                 // as written in the document (first occurrence)
  context: string;                  // plain-text excerpt
  occurrences: number;
  defanged: boolean;
  status: CandidateStatus;
  existing_observable_id: string | null;
  existing_confidence: number | null;
  already_attributed: boolean;
  allowlisted: boolean;
  allowlist_matches: string[];
  warnings: string[];               // machine codes, see Extraction rules
}

interface ExtractionPreview {
  report_id: string;
  sources: ExtractionSource[];
  candidates: ExtractionCandidate[]; // sorted: type, then value
  truncated: boolean;
  counts: { total: number; new: number; existing: number; invalid: number };
}

interface ImportRequest {
  confidence: number;               // required, 0..100
  items: { type: string; value: string }[]; // 1..1000, unique by (type, value)
}

interface ImportResult {
  created: number;                  // new observables
  attributed_existing: number;      // existing observables newly linked/attributed
  already_attributed: number;       // no-op, already imported from this report
  observables: { id: string; type: string; value: string; confidence_score: number; created: boolean }[];
}
```

Import validation (422 with a `detail` naming the offending items, nothing
written):
- `items` empty, more than 1000 entries, or duplicate entries.
- Any item that is not a valid (non-`invalid`) candidate in the server's
  re-extraction of the report at import time, including values only valid
  after the client's own normalization. Detail code: `not_a_candidate`.
- `confidence` missing or outside 0–100.

Unsupported-only documents have no candidates, so every import against them is
rejected with `not_a_candidate`.

422 `detail` shape (pinned after frontend review): always the FastAPI
validation shape, a list of `{ type, loc, msg, ... }`. Pydantic body errors
(empty, too many, duplicates, confidence) use FastAPI's own entries. A
`not_a_candidate` rejection is one entry:

```json
{ "type": "not_a_candidate", "loc": ["body", "items"],
  "msg": "2 item(s) are not valid candidates extracted from this report: url http://x, ...",
  "items": [{ "index": 0, "type": "url", "value": "http://x" }] }
```

`msg` is human-readable and names up to 20 items. The frontend shows every
entry's `msg` (not just the first), and may use `items` to highlight rows.

## Frontend

- Report detail page (`ReportDetailPage.tsx`): an admin-only **Extract
  indicators** button. It calls `/extract` and opens a review view (a dialog
  or a dedicated panel; the implementer picks one consistent with existing
  components). Non-admins don't see it.
- The review view shows a table: checkbox, type, normalized value, original
  text (only when it differs from value), context, status badge
  (new / existing / invalid), "already linked" marker, defanged marker,
  allowlist match, and warnings rendered as readable text. All values are
  plain text and never links. Long values wrap or truncate with a full-text
  title.
- The source list shows each source's status, with a clear message for
  unsupported or scanned documents: "PDF text extraction is not available
  yet; paste the report text into the report content to extract indicators."
- Default selection: `new` and `existing` candidates that are not
  `already_attributed` and not `allowlisted`. `invalid` rows cannot be
  selected. Select-all / select-none apply to the selectable rows; filtering
  by type is optional.
- Confidence input: number 0–100, default 50, with help text: "Applies to
  newly created observables only. Existing observables keep their current
  confidence and sources. This is your judgment, not a score derived from the
  report."
- Before confirming, show an export-eligibility notice: "Imported indicators
  can appear in blocklist exports and export profiles under current policies
  (for example, the default blocklist threshold of 70). Allowlisted values
  stay excluded from exports."
- Confirm button: "Import N indicators". It is disabled at N = 0 and while
  submitting. Nothing is imported until the analyst clicks it. On success,
  show a toast with the created / attributed / already-linked counts, close
  the view, and refetch the report so the linked observables list updates.
  On 422, show the server `detail` and keep the selection.
- Observable detail page: the existing Reports section keeps working; no
  change required.
