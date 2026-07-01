# Remaining Screens (Observables, Detail, Feeds, Settings) — Plan & Decisions

> Lean plan for the 4 remaining redesign screens, stacked on the dashboard branch. Frontend-only — the backend already exposes everything needed. Build subagent-driven; each screen reviewed before moving on. Match the screenshots in `design_handoff_ui_refresh/screens/`.

**Branch:** `redesign/ui-refresh-screens` (off dashboard `b139292`).

## Global constraints
- **Match the screenshots structurally** (per-screen PNG in `design_handoff_ui_refresh/screens/`), using foundation tokens (`bg-surface`/`card`, `text-muted-foreground`, `border-border`, `bg-brand`, `cat-*`, `conf-*`) and existing `components/ui/` primitives (incl. the new Slider/Popover/Tabs). No parallel styling system.
- **Mono (`font-mono`)** for all observable values, hashes, IPs, counts/scores, cron strings, key prefixes, raw JSON.
- **No fabricated data or functionality.** Wire only to real endpoints; render an unbacked control (Block) disabled rather than faking it.
- **Roles are `admin`/`user`** (Members tab — NOT Analyst/Read-only).
- **Decay is LINEAR** (`max(floor, native − weeks·rate)`), caption must say so — never "half-life".
- Frontend tests `npm run test`; keep all green. `npm run build` clean per task.

## Gap resolutions (from audit)
1. **Detail page** — build new route `/observables/:id`; `getObservable`/`useObservable` already exist.
2. **Block action** — no backend endpoint → render the Block button **disabled** with a title/tooltip ("blocklist export covers this"); do not invent an action.
3. **Settings General** — `getConfig()` already returns `instance_name`/`observable_retention_days`/`default_export_format` (foundation); just render them (read-only). Update `getConfig` return type to `InstanceConfig`.
4. **Export** — add `src/api/export.ts` (URL builders) + the export popover; items are authenticated download links to the existing `/api/v1/export/blocklist/{type}`, `/export/json`, `/export/text` endpoints (JWT cookie auths the navigation). Pass current filters (confidence_min, type, source/feed_id) as query params.
5. **Source filter** — the `source` param (feed UUID | "manual" | unset) drives the dropdown (All / Manual only / each feed). `feed_id` unused. Source list comes from `useFeeds()`.
6. **Decay chart** — no history endpoint; project the curve client-side from each source's `native_confidence`, its `last_seen_by_feed` age, and decay params from `/settings/config` using the linear formula. Native-max = max(native_confidence); decayed = `confidence_score`.

## Screen task breakdown (build order)

### A. Observables (`/observables`) — screenshot `2-observables-dark.png` (+ `7-observables-light.png`, `2b` export)
- A1 `ObservableFilters` redesign: search-by-value, **Type** select, **Source** select (from `useFeeds()` + Manual/All), **Min confidence** Slider (0–100 step 5, live mono readout), **Export** split-button → `Popover` (Firewall blocklist: IP/Domain/URL + Full JSON; each row shows endpoint path + download icon → links from `api/export.ts`).
- A2 `ObservableTable` redesign: columns Type (icon+colored chip), Value (mono, truncate), Confidence (mini bar + mono score + band label, band-colored), Sources (name chips, "Manual" if none, "+N" overflow), Last seen (relative, right), caret; row hover `bg-hover`; **whole row click → `/observables/:id`**.
- A3 results-card header (count + Sort select + asc/desc toggle) + `Pagination` (page size 10).
- A4 `ObservablesPage` assembly (filters card → results card); keep create dialog.
- A5 `api/export.ts` (build export URLs from filters).

### B. Observable Detail (`/observables/:id`) — `3-detail-dark.png`, `3b-detail-raw-dark.png` — NEW
- B1 route in `App.tsx` + `ObservableDetailPage` skeleton (back link, `useObservable(id)`).
- B2 header card: type icon tile, type chip + band-confidence chip, value (large mono + **copy** button → check 1.4s), **Block** (outline, disabled), **Export** (brand, wired); 4-cell key-facts strip (First seen, Last seen, Sources count, Confidence colored).
- B3 confidence ring (SVG donut, band-colored) + dual readout **decayed vs native max**; decay **area chart** (recharts) projecting native→decayed using `/settings/config` params; caption states the linear model.
- B4 `Tabs` (Sources | Raw JSON): Sources table (Feed, Native conf mono band-colored, type chip, first/last seen by feed); Raw JSON `<pre>` mono + copy + `GET /api/v1/observables/:id` label.

### C. Feeds (`/feeds`) — `4-feeds-dark.png`
- C1 4 summary cards (Configured, Enabled, Errors 24h, Observables) from `useFeeds()` (+ maybe `/stats`).
- C2 filter segmented control (All / API / File / Scraper) + Add Feed.
- C3 `FeedCard` redesign: type icon tile, status dot, name, type chip, "API key required" chip (yellow, when applicable), description, meta row (count, cron, default confidence, status+last run), **Run now**, enable/disable **Toggle** (brand), overflow menu; disabled cards dim ~0.62.
- C4 `FeedsPage` assembly (summary → filter → card list).

### D. Settings (`/settings`) — `5-settings-apikeys-dark.png`, `5b-settings-members-dark.png`
- D1 left sub-nav `Tabs` (API keys / Members / General) — SettingsPage shell.
- D2 API keys: header + Create; curl example (`X-API-Key`); table Name, Key (masked prefix mono), Role chip, Created, Last used, delete; hint on "Default Admin Key".
- D3 Members: invite + list (avatar initials, name, email mono, role chip **Admin/User**, last login).
- D4 General: read-only rows — Instance name, **Confidence decay** (linear params from config), Observable retention, Default export format. (Add the instance fields the current GeneralSettings omits.)

## Delivery
Build A→B→C→D, each reviewed. Then a whole-branch review + one PR (stacked on the dashboard PR #4), or split per-screen if preferred.
