# Tags and enforced TLP markings (issue #15) — shared contract

Backend and frontend are built in parallel against this contract. Neither side
changes it unilaterally; raise a question to the coordinator instead.

**Status:** the policy in this document was approved by the owner on 2026-11-01
(design checkpoint in #15). Decisions: ad-hoc exports are `internal` scope;
Unspecified is exportable to `internal` destinations only.

Scope guardrail: no cases, collections, investigations or recipient/organization
management. Tags are flat labels. TLP is a **sharing policy**, not a confidence
score and not access control: every authenticated user can still *view* every
marking in the app.

## TLP values

String enum `Tlp` (FIRST TLP 2.0), stored as these exact strings:

| value | rank | meaning shown in UI (one line) |
|---|---|---|
| `clear` | 0 | Disclosure is not limited. |
| `green` | 1 | Share within your community, not publicly. |
| `amber` | 2 | Share within your organization and its clients on a need-to-know basis. |
| `amber+strict` | 3 | Share within your organization only. |
| `red` | 4 | Named recipients only; does not leave this application. |

**Unspecified** is SQL `NULL` / JSON `null`. It is not a rank and is never shown
as CLEAR. Labels: `TLP:CLEAR`, `TLP:GREEN`, `TLP:AMBER`, `TLP:AMBER+STRICT`,
`TLP:RED`, `Unspecified`.

## Where markings live (migration `009`)

All new columns are nullable; `NULL` = Unspecified. Existing rows stay `NULL`.
Do **not** backfill any marking.

| table | column | set by |
|---|---|---|
| `feeds` | `tlp varchar(16) null` | admin on feed create/edit; applies to everything that feed contributes |
| `reports` | `tlp varchar(16) null` | report create/edit (same permission as editing the report). The report's attachment inherits it. |
| `observables` | `manual_tlp varchar(16) null` | `POST /observables` (manual create). Re-creating an existing observable keeps the **more restrictive** of old and new (a specified value replaces NULL, never the reverse). |
| `observables` | `tlp_override varchar(16) null`, `tlp_override_reason varchar(500) null`, `tlp_override_set_at timestamp null`, `tlp_override_set_by_id uuid null FK users ON DELETE SET NULL` | admin reclassification (below) |
| `export_profiles` | `destination varchar(16) not null default 'internal'` | admin; CHECK in (`internal`,`community`,`public`) |

CHECK constraints: every tlp column is NULL or one of the five values;
`tlp_override_reason` and `tlp_override_set_at` are non-null iff `tlp_override`
is non-null. Use `batch_alter_table` (SQLite + PostgreSQL), like `007`/`008`.

## Effective marking

One function owns the rule (e.g. `services/tlp.py`). Inputs for an observable:

- the `tlp` of every feed in its `observable_sources`,
- the `tlp` of every report linked via `report_observables`,
- `manual_tlp`, **only if it is non-null or the observable has no feed and no report** (a feed-only observable is not "unspecified" just because nobody created it manually).

```
if tlp_override is set:            effective = tlp_override
else:
  specified = non-null inputs
  hi = max rank of specified (or none)
  if any input is NULL (Unspecified) and (hi is none or hi < amber):
                                   effective = Unspecified
  else:                            effective = hi
```

So the most restrictive marking always wins. Unspecified "poisons" CLEAR/GREEN
down to Unspecified (we don't know it was shareable), but AMBER and above still
dominate. Imports, feed runs and new links therefore **cannot downgrade** an
observable: adding an input can only keep or raise restriction. The only way to
loosen it is an explicit admin action: an override, or editing a feed/report
marking (see "Downgrades").

Compute at read/export time in SQL (no stored effective column that can drift),
the same way allowlisting is matched at read time. Exports must filter on it
**before** limits, like the allowlist.

### Report effective marking

A report's marking is its own `tlp` field (reports have one origin). The
attachment uses the report's marking. Linked observables do not change the
report's marking.

### Reclassification (authorized override)

| Method | Path | Auth | Body | Response |
|---|---|---|---|---|
| PUT | `/observables/{id}/tlp-override` | admin | `{ "tlp": Tlp \| null, "reason": str 1–500 (trimmed, required) }` | 200 `ObservableResponse`; 404; 422 |
| DELETE | `/observables/{id}/tlp-override` | admin | | 200 `ObservableResponse`; idempotent |

`tlp: null` in the override means "explicitly Unspecified" is **not** allowed:
422. An override is always one of the five values. It may loosen or tighten.

### Downgrades

Changing a feed's or report's `tlp` to a **less restrictive** value (lower
rank, or specified → NULL) requires a `tlp_change_reason` (1–500 chars) in the
same request body; without it, 422 with a clear message. Tightening needs no
reason. Store nothing extra for these reasons beyond logging them via the
existing logger at INFO (no audit-log system in scope). Feed `tlp` is admin-only
(feeds are admin-managed already).

## Destinations and enforcement

One function decides: `is_shareable(effective: Tlp | None, destination) -> bool`.

| destination | allowed effective markings |
|---|---|
| `internal` (this organization's own controls: firewalls, SIEM) | Unspecified, clear, green, amber, amber+strict |
| `community` | clear, green |
| `public` | clear |
| `external_ai` (code-only, not a profile option) | clear, green |
| any unknown/unsupported destination | nothing (fail closed) |

**RED never leaves through any export, profile, or API-key path.**

Enforcement points (backend, not UI):

1. `GET /export/json`, `/export/text`, `/export/blocklist/{type}`: `internal` scope. Exclude RED. Cached results must never bypass this: apply the TLP filter after cache read the same way the allowlist is (or drop caching for these endpoints). Changing a marking or override must be reflected on the next request.
2. Export profile preview and download: profile `destination`. Preview count must still equal download count.
3. `GET /reports/{id}/attachment`: if the report's marking is `red`, reject API-key callers with 403 (`detail` names the TLP reason); interactive user sessions may download. Every attachment response includes header `X-TLP-Marking: <value or "unspecified">`. Report JSON (`ReportDetail`/`ReportSummary`) is in-app viewing and is not filtered.
4. External AI: no code path sends instance data to a provider today (#13 is config only). Add the `external_ai` destination to the gate with tests, plus a helper `filter_for_external_ai(observables|reports)` that future features must call. Do not add any AI feature.
5. Allowlist exclusion is independent and unchanged: a value is exported only if it passes **both** the allowlist and the TLP check.

## Tags

`tags`: `id uuid pk`, `name varchar(50) unique not null`, `created_at`.
Join tables `observable_tags(observable_id, tag_id)` and `report_tags(report_id, tag_id)`, composite PKs, both FKs `ON DELETE CASCADE`, index on `tag_id`.

Normalization (backend is the authority; the frontend mirrors it for UX):
trim, collapse internal whitespace runs to a single `-`, lowercase (Unicode
`casefold`). After normalization: 1–50 chars, allowed `[a-z0-9._:/-]` only
(otherwise 422 with a message). Duplicates after normalization are the same
tag: creating an existing name returns the existing tag (200, not 409);
assigning an already-assigned tag is a no-op.

| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | `/tags` | authenticated | `[{id, name, observable_count, report_count}]`, sorted by name; optional `q` prefix filter |
| POST | `/tags` | admin | `{name}` → 201 new / 200 existing |
| DELETE | `/tags/{id}` | admin | 204; removes all assignments |
| PUT | `/observables/{id}/tags` | admin | `{tags: string[]}` (names; created on the fly, normalized) → replaces the set; 200 `ObservableResponse` |
| PUT | `/reports/{id}/tags` | admin | same, returns `ReportDetail` |

Filtering:
- `GET /observables?tag=a&tag=b` and `GET /reports?tag=…`: match **any** listed tag (OR). Also `tlp=<value|unspecified>` (repeatable) on `/observables` (effective marking) and `/reports`.
- Ad-hoc exports accept the same repeatable `tag` parameter.
- Export profiles gain `tags: string[]` (names, normalized; empty = no tag filter; stored as a `export_profile_tags` join table to existing tags, deleting a tag referenced by a profile is **409**, same fail-closed rule as referenced feeds). Profile filter = any listed tag.

## API payload additions

`ObservableResponse` (list and detail):

```ts
tags: string[];                    // sorted names
manual_tlp: Tlp | null;
effective_tlp: Tlp | null;         // null = Unspecified
tlp_sources: Array<{               // every input, so original restrictions stay visible
  kind: "feed" | "report" | "manual";
  id: string | null;               // feed/report id; null for manual
  name: string;                    // feed name / report title / "Manual"
  tlp: Tlp | null;
}>;
tlp_override: { tlp: Tlp; reason: string; set_at: string; set_by: string | null } | null;
```

`ReportSummary`/`ReportDetail`: `tlp: Tlp | null`, `tags: string[]`. Report
create/patch accept `tlp` (+ `tlp_change_reason` when downgrading on patch).
Feed responses/requests: `tlp` (+ `tlp_change_reason` when downgrading).
Export profile: `destination`, `tags`.

`ExportObservable` (JSON export) gains `tlp: Tlp | null` and `tags: string[]`.
Text/blocklist formats are unchanged (one value per line).

`ExportProfilePreview` becomes:

```ts
{ count: number; excluded_allowlisted: number;
  excluded_by_tlp: { unspecified: number; clear: number; green: number; amber: number; "amber+strict": number; red: number };
  sample: string[] }
```

`excluded_by_tlp` counts rows that pass every other profile filter **and the
allowlist** but fail the destination check, keyed by effective marking. Zero
entries are present (all six keys always).

Ad-hoc export responses add header `X-TLP-Excluded: <n>` (rows withheld by TLP).

## Rollout and backward compatibility

- Migration leaves every marking NULL and every profile `internal`. Since
  `internal` allows Unspecified, **all existing exports return exactly what they
  returned before** until an admin marks something RED or creates a
  community/public profile.
- Preview shows exclusions per marking before an admin switches a profile's
  destination; the UI explains them.
- Downgrade migration (`009` → `008`) drops the new columns/tables.
- A docs section in `README.md` ("Tags and TLP") states: what each marking
  allows per destination, that Unspecified is internal-only, that TLP is not
  access control, that RED never leaves through exports/API keys, and the
  rollout behavior above.

## Frontend

- Shared `TlpBadge` (colors per FIRST: CLEAR white/outlined, GREEN green, AMBER
  amber, AMBER+STRICT amber with a "STRICT" label, RED red; Unspecified neutral
  grey dashed outline, text "Unspecified"). Tooltip = the one-line meaning above.
  Must work in light and dark appearance.
- Observables list: TLP column (effective) and tags; filters for tag (multi,
  any) and TLP. Observable detail: effective badge prominently near the title,
  "Why this marking" list of `tlp_sources`, override badge with reason/user/
  time, admin-only override and clear controls (reason required), admin tag
  editor; read-only tag chips for others.
- Reports list/detail: TLP badge and tags, filters; attachment section shows
  the badge and the note "RED attachments can't be downloaded with API keys".
  Report create/edit form: TLP select (Unspecified default) and tags (admin);
  downgrade asks for a reason.
- Feeds: TLP select on create/edit (admin); downgrade asks for a reason.
- Settings → Export profiles: destination select with explanation of what each
  allows; tag filter; preview shows `excluded_by_tlp` as readable reasons
  ("3 excluded: TLP:RED never leaves the application").
- Do not imply enforcement that does not exist: no badge copy like "protected"
  or "encrypted".

## Verification

Backend tests: each marking + Unspecified persists and round-trips; effective
rule (multi-source, Unspecified poisoning, AMBER dominance, manual input rule,
override loosen/tighten, override clear); imports/feed runs/new links cannot
downgrade; downgrade-without-reason 422; destination matrix for every marking;
RED excluded from all three ad-hoc endpoints **including after a cached
response exists**; profile preview == download counts with `excluded_by_tlp`;
allowlisted values excluded independently of TLP; attachment API-key RED 403
and header; external_ai gate; tags normalization/duplicates/limits/admin
guards/filters/profile tag filter/409 on referenced delete; migration up/down.
Frontend tests for badges, filters, override/tag/admin controls, preview
feedback. Run full pytest, Vitest, TypeScript/Vite build, Alembic offline SQL.
