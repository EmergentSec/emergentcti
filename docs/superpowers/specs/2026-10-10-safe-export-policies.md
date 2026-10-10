# Safe export policies — implementation contract

**Status:** Implemented on `feature/safe-export-policies`; live PostgreSQL and isolated Docker preview validation passed. User reviewed the isolated preview and approved PR submission.

## Scope

First roadmap slice: reversible allowlisting (option A), actual retention enforcement, saved export profiles. Tags, TLP, STIX/TAXII/MISP, audit logs and runtime configuration editing remain follow-ups.

## Allowlist

Keep all matching observables and their sources on ingestion. Match at read/export time so adding/removing an entry is reversible immediately. All existing JSON, text and blocklist exports and profile downloads exclude matches. No research bypass in this slice. Avoid serving cached results with stale policy: use authoritative matching on every export (disabling export caching is acceptable).

An entry has `id`, `kind` (`exact`, `cidr`, `domain_suffix`), `value`, `observable_type`, `reason`, `created_at`, `updated_at`. Exact requires a type; exact ip-addr requires a single address (use CIDR for ranges). Range-valued IP observables are suppressed if they overlap an allowlisted CIDR or contain an exact allowlisted IP, preventing protected addresses from being blocked by a larger range. CIDR is IPv4/IPv6 only, canonicalized using ipaddress with strict=False; set type to ip-addr. Domain suffix applies only to domain-name, matching the domain itself and subdomains with label boundaries, case-insensitive, canonical lowercase and trailing-dot normalization. Domain exact uses the same hostname normalization; IP exact canonicalizes IPs. Other exact values are literal, type-specific. Validate inputs and reject duplicate canonical policies with 409. Canonical values are capped at 2048 UTF-8 bytes to stay safely within PostgreSQL's unique-index tuple limit. Reason is required, nonempty, max 500 chars. No implicit URL/email host matching.

Authenticated reads, administrator mutations (existing API keys retain existing admin behavior). Routes `/api/v1/allowlist`: GET list (array), POST (201), DELETE /{id} (204). No editing in first slice: delete and recreate. Observable response adds `allowlisted: bool` and `allowlist_entry_ids: UUID[]`, including list and detail. Do not persist a boolean that can drift.

## Export profiles

Saved shared profiles with `id`, `name` (unique, 1–100 chars), `description` (max 500), `format` (text/json), `type` (nullable ObservableType), `confidence_min` (0–100, default 70), `max_age_days` (nullable, 1–36500), `feed_id` (nullable UUID), timestamps. Feed deletion must not silently broaden export policy; prevent deleting referenced feeds or otherwise fail closed. Profiles are configuration, not public authentication tokens.

Routes `/api/v1/export/profiles`: authenticated GET list (array); admin POST (201), PUT /{id}, DELETE /{id} (204). Authenticated GET /{id}/download evaluates saved filters against current data/policy and produces text or existing JSON export shape. GET /{id}/preview returns `{count: number, excluded_allowlisted: number, sample: string[]}` (at most 20 values); excluded_allowlisted is counted among indicators matching other profile filters. Use stable authenticated URLs compatible with X-API-Key for firewall clients. No unadvertised truncation of profile downloads (text OR JSON): profiles export all eligible rows so preview count agrees with download count. The ordinary `/export/json` endpoint retains its explicit `limit` parameter semantics. Exclude allowlisted rows BEFORE limits. Skip control-character-containing values in all line-based exports to prevent extra-line injection; JSON retains literal values. Text profile preview uses the same eligibility rules as download.

## UI

Add Allowlist and Export profiles Settings tabs, available for read to authenticated users, with mutation controls only for admins. Provide create/delete entry controls, clear policy explanation, duplicate/error feedback. Profiles offer create/edit/delete, filter controls, preview, copy download URL and download. Show allowlisted badge on observable list/detail; replace disabled Block detail button with admin-only Allowlist action requiring a reason (exact-value for individual indicators, CIDR for range-valued IPs). Removing policy uses Settings (multiple matching rules can apply). Existing export behavior is compatible except intentional suppression of matches.

## Retention

`OBSERVABLE_RETENTION_DAYS` currently defaults to 180: implement daily scheduler job at 03:00 UTC, registered on startup (fixed wall-clock schedule so restarts do not postpone enforcement), deleting rows whose last_seen (or created_at when unknown) is strictly older than cutoff. Delete associated source rows safely, retain allowlist entries and profiles. 0 disables retention; reject negative configuration. Manual and allowlisted indicators are subject to the same policy; UI/docs explicitly distinguish reversible allowlisting from irreversible retention deletion. Use bounded batches, transactions, error rollback/logging and invalidate affected caches after committed deletions. Retention remains environment-configured; no run-now destructive UI.

## Verification

Backend tests: typed exact/CIDR/domain boundaries/IPv6/validation, admin guards, suppression across ALL exports and cached policy changes, reversibility, exclude-before-limit, profile CRUD/filtering/preview/download, referenced feed deletion safety. Retention tests: old/recent/null-date, source cleanup, disabled/idempotence, failure safety; scheduler wiring. Frontend tests: policy controls, admin restrictions, error feedback, previews/URLs, observable status/action. Run full pytest, Vitest, TypeScript/Vite build, diff whitespace checks, Alembic offline SQL (and online if PostgreSQL available).

## Validation result

- Backend: 305 passed against PostgreSQL, including all five opt-in checks; none skipped.
- Frontend: 258 passed across 36 files; TypeScript/Vite production build passed.
- Alembic base→004 upgrade and 004→003 downgrade SQL generation passed; whitespace checks passed.
- `tests/test_postgres_policies.py` covers production migration functions in isolated schemas, retention row locking, source cleanup/policy preservation, server-side export cursors, profile FK RESTRICT, and async-safe feed response serialization. Run with `CTI_TEST_POSTGRES_URL`.
- Isolated Docker Compose preview: all four services healthy; fresh database upgraded online through 004. Browser checks passed for login, observable detail allowlisting, Settings deep links, profile creation and preview. Live API checks passed for text/JSON downloads, count agreement, anonymous download rejection, CIDR/suffix matching, cached suppression/reversal, custom feed create/edit, and referenced-feed deletion protection. Retention disabled in the preview; only synthetic indicators retained for review.
- Live validation fixed IPv4 frontend health checking and pre-existing custom-feed create/update response serialization errors (implicit async ORM IO); added PostgreSQL regression coverage.
- Independent read-only review completed; high/medium code findings addressed.
- Existing frontend dependency audit warnings remain outside this feature: six runtime dependency findings (two high, four moderate). Dependency upgrades need a separate review before public deployment.

## Follow-ups

Tags/TLP/STIX/TAXII/MISP, audit logs, runtime editing, public/scoped integration credentials and the optional research export remain out of scope. IDNA equivalence and IPv4-mapped IPv6 equivalence are not inferred; users must supply matching forms. Non-domain/IP exact values deliberately remain case/whitespace-sensitive. Broad CIDRs and suffixes are allowed policy choices, not automatically narrowed. Profile browser downloads use authenticated links like existing exports (not toast-based download error handling).
