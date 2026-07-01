# Dashboard + Global Layout — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Replace the placeholder dashboard + layout with the redesigned **Global Layout** (branded sidebar + sticky topbar with a working theme toggle) and the **Dashboard screen** (KPI row, 14‑day ingestion chart, type donut, feed‑status table, confidence‑distribution bars), wired to real `/api/v1/stats` data.

**Architecture:** One small backend addition (`daily_ingest_14d` on `/stats`) feeds the new ingestion chart; everything else reads fields the foundation already exposes. The frontend rebuilds `Sidebar`/`Header` and the dashboard into focused presentational components driven by the existing `useDashboard()` react-query hook. Charts use **recharts** (installed); icons use **@phosphor-icons/react** (installed); theme toggle uses the foundation's `useTheme()`.

**Tech Stack:** Backend — FastAPI, SQLAlchemy 2 async, pytest (`uv run --extra dev pytest`). Frontend — React 18 + TS + Vite, Tailwind (brand tokens from the foundation), react-query, recharts, phosphor; tests via `npm run test` (vitest + happy-dom + @testing-library/react).

## Global Constraints

- **Match the screenshots, not just the tokens.** Primary targets: `design_handoff_ui_refresh/screens/1-dashboard-dark.png` and `…/6-dashboard-light.png`. Open them. The README note is explicit: the gap is structural — build the real layout/components, don't re-theme the old ones.
- **No parallel styling system.** Use Tailwind + the foundation tokens (`bg-background`, `bg-card`/`bg-surface`, `text-foreground`, `text-muted-foreground`, `border-border`, `bg-brand`/`text-brand`, `bg-surface2/3`, categorical `cat-*`, confidence `conf-*`) and the existing `components/ui/` primitives.
- **Mono for numbers.** All KPI values, counts, percentages, and the donut center use `font-mono` (JetBrains Mono). Sans (Hanken Grotesk) for labels/titles.
- **No fabricated data.** Only render a KPI delta/subtitle when it is computable from real API data. Specifically: "Ingested vs avg" is computed from `daily_ingest_14d`; the feed-error subtitle is the failing feed's name from `feeds_health`. Do NOT invent week-over-week deltas or "N need API key" — omit subtitles you can't back with data.
- **Sidebar 236px, brand-tinted active item** (`color-mix(in srgb, var(--brand) 13%, transparent)` background, brand text, weight 700). **Topbar sticky, ~60px, blurred** (`backdrop-blur`), border-bottom.
- **Roles are `admin`/`user`** (foundation decision); show the role from `useAuth()` verbatim.
- Backend tests: `uv run --extra dev pytest`. Frontend tests: `npm run test`. Both must stay green.
- Don't bump dependency majors.

---

## File Structure

**Backend**
- `src/cti/api/v1/stats.py` — add `daily_ingest_14d` (14-day daily new-observable series, zero-padded).

**Frontend — types/data**
- `src/types/dashboard.ts` — add `daily_ingest_14d: { date: string; count: number }[]` to `DashboardStats`.

**Frontend — layout (rebuild)**
- `src/components/layout/Sidebar.tsx` — branded nav (phosphor icons, live counts from stats, brand-active), API-online + user footer.
- `src/components/layout/Header.tsx` — title+subtitle, search (⌘K), theme toggle, Add-Observable; consume `useAuth()` + `useTheme()`.
- `src/components/layout/AppLayout.tsx` — adjust padding to 236px sidebar; sticky topbar.

**Frontend — dashboard (rebuild `src/components/dashboard/`)**
- `KpiCards.tsx` — the 4-up KPI row.
- `IngestionTrend.tsx` — recharts area chart from `daily_ingest_14d`.
- `TypeDonut.tsx` — recharts donut from `by_type` + legend with %.
- `FeedStatusTable.tsx` — redesigned feed-health table (replaces `RecentFeedRuns` usage).
- `ConfidenceBars.tsx` — 4 band bars from `confidence_distribution`.
- `src/pages/DashboardPage.tsx` — assemble the grid; drop old `StatsGrid`/`TypeBreakdown`/`RecentFeedRuns`.
- `src/lib/dashboardFormat.ts` — small pure helpers (compact number, % of total, vs-avg delta) — unit-tested.

---

## Task 1: Backend — 14-day daily ingestion series on `/stats`

**Files:**
- Modify: `src/cti/api/v1/stats.py`
- Test: `tests/test_api/test_stats.py` (append)

**Interfaces:**
- Produces: `/api/v1/stats` gains `"daily_ingest_14d": [{ "date": "YYYY-MM-DD", "count": int }, ...]` — exactly 14 entries, oldest→newest, days with no successful runs padded to `count: 0`.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_api/test_stats.py
@pytest.mark.asyncio
async def test_stats_includes_14d_ingestion_series(client, db_session):
    resp = await client.get("/api/v1/stats")
    assert resp.status_code == 200
    series = resp.json()["daily_ingest_14d"]
    assert isinstance(series, list)
    assert len(series) == 14
    assert all(set(p) == {"date", "count"} for p in series)
    # oldest first, newest last
    assert series[0]["date"] < series[-1]["date"]
    assert all(isinstance(p["count"], int) for p in series)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --extra dev pytest tests/test_api/test_stats.py::test_stats_includes_14d_ingestion_series -v`
Expected: FAIL — `KeyError: 'daily_ingest_14d'`.

- [ ] **Step 3: Compute the series and add it to the response**

In `src/cti/api/v1/stats.py`, after the existing `feed_errors_24h` block and before assembling `result`, add (uses `datetime`, `timedelta`, `UTC` already imported; `func` already imported):

```python
    # 14-day daily new-observable series (zero-padded, oldest -> newest)
    from datetime import date as _date

    start_day = (datetime.now(UTC) - timedelta(days=13)).date()
    daily_rows = await db.execute(
        select(
            func.date(FeedRun.completed_at).label("day"),
            func.coalesce(func.sum(FeedRun.observables_new), 0).label("count"),
        )
        .where(
            FeedRun.status == FeedRunStatus.SUCCESS,
            FeedRun.completed_at >= datetime.combine(start_day, datetime.min.time(), UTC),
        )
        .group_by(func.date(FeedRun.completed_at))
    )
    # SQLite returns the grouped day as a string; Postgres returns a date — normalize to ISO string.
    counts_by_day: dict[str, int] = {}
    for row in daily_rows.all():
        day = row.day
        key = day if isinstance(day, str) else day.isoformat()
        counts_by_day[key] = int(row.count or 0)

    daily_ingest_14d = [
        {
            "date": (start_day + timedelta(days=i)).isoformat(),
            "count": counts_by_day.get((start_day + timedelta(days=i)).isoformat(), 0),
        }
        for i in range(14)
    ]
```

- [ ] **Step 4: Add to the `result` dict**

Add the key alongside the others (e.g. right after `"feed_errors_24h": feed_errors_24h,`):

```python
        "daily_ingest_14d": daily_ingest_14d,
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run --extra dev pytest tests/test_api/test_stats.py -v`
Expected: PASS (the new test + the existing stats test).

- [ ] **Step 6: Commit**

```bash
git add src/cti/api/v1/stats.py tests/test_api/test_stats.py
git commit -m "feat(stats): add 14-day daily ingestion series"
```

---

## Task 2: Frontend type + format helpers

**Files:**
- Modify: `src/types/dashboard.ts`
- Create: `src/lib/dashboardFormat.ts`
- Test: `src/lib/dashboardFormat.test.ts`

**Interfaces:**
- Consumes: Task 1's `daily_ingest_14d`.
- Produces: `DashboardStats.daily_ingest_14d: { date: string; count: number }[]`; and pure helpers `compactNumber(n: number): string` (e.g. `1482930 → "1.48M"`, `11 → "11"`), `pct(part: number, total: number): number` (rounded integer percent, 0 when total 0), `vsAvgDelta(today: number, series: {count:number}[]): number | null` (percent diff of `today` vs the mean of the series, `null` if series empty or mean 0).

- [ ] **Step 1: Write the failing test**

```ts
// src/lib/dashboardFormat.test.ts
import { describe, it, expect } from 'vitest';
import { compactNumber, pct, vsAvgDelta } from './dashboardFormat';

describe('dashboardFormat', () => {
  it('compactNumber', () => {
    expect(compactNumber(1482930)).toBe('1.48M');
    expect(compactNumber(12408)).toBe('12.4K');
    expect(compactNumber(11)).toBe('11');
  });
  it('pct', () => {
    expect(pct(43, 100)).toBe(43);
    expect(pct(1, 0)).toBe(0);
  });
  it('vsAvgDelta', () => {
    expect(vsAvgDelta(120, [{ count: 100 }, { count: 100 }])).toBe(20);
    expect(vsAvgDelta(100, [])).toBeNull();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run (in `frontend/`): `npm run test -- dashboardFormat`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement the helpers**

```ts
// src/lib/dashboardFormat.ts
export function compactNumber(n: number): string {
  if (n < 1000) return String(n);
  if (n < 1_000_000) return `${(n / 1000).toFixed(n < 10_000 ? 1 : 1)}K`.replace('.0K', 'K');
  return `${(n / 1_000_000).toFixed(2)}M`.replace(/\.?0+M$/, 'M');
}
export function pct(part: number, total: number): number {
  if (!total) return 0;
  return Math.round((part / total) * 100);
}
export function vsAvgDelta(today: number, series: { count: number }[]): number | null {
  if (!series.length) return null;
  const mean = series.reduce((s, p) => s + p.count, 0) / series.length;
  if (!mean) return null;
  return Math.round(((today - mean) / mean) * 100);
}
```

- [ ] **Step 4: Extend the type**

In `src/types/dashboard.ts`, add to `DashboardStats`:
```ts
  daily_ingest_14d: { date: string; count: number }[];
```

- [ ] **Step 5: Run test to verify it passes**

Run (in `frontend/`): `npm run test -- dashboardFormat`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/types/dashboard.ts src/lib/dashboardFormat.ts src/lib/dashboardFormat.test.ts
git commit -m "feat(dashboard): daily_ingest_14d type + format helpers"
```

---

## Task 3: Redesigned Sidebar

**Files:**
- Modify: `src/components/layout/Sidebar.tsx`
- Test: `src/components/layout/Sidebar.test.tsx`

**Reference:** the left rail in `screens/1-dashboard-dark.png` / `6-dashboard-light.png`.

**Interfaces:**
- Consumes: `useDashboard()` (for nav counts: Observables = `compactNumber(total_observables)`, Feeds = `feeds_enabled/total_feeds`), `useAuth()` (user name, role, logout), `useTheme()` not needed here.
- Produces: `<Sidebar />` (no props).

**Build to spec:**
- 236px fixed rail, `bg-surface`/`bg-card`, right border.
- Header: `<EmergentLogo size={28} />` + wordmark "EmergentCTI" / "Threat Intelligence" (subtitle `text-muted-foreground` uppercase 11px).
- Nav (phosphor icons): Dashboard (`SquaresFour`), Observables (`CrosshairSimple`) with right-aligned mono count `1.48M`, Feeds (`Rss`) with mono `11/13`, Settings (`GearSix`). Use `NavLink`; active item: brand-tinted bg via `style={{ background: 'color-mix(in srgb, var(--brand) 13%, transparent)' }}`, `text-brand font-bold`.
- Footer (bottom, pinned): a green status dot + "API online" + version `v2.0.0` (mono, `text-muted-foreground`); below it the user row — circular avatar with initials (derive from `user.username`), name, role (`text-muted-foreground` capitalize), and a sign-out icon button (`SignOut`) calling `logout()`.

- [ ] **Step 1: Write the failing test**

```tsx
// src/components/layout/Sidebar.test.tsx
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, it, expect, vi } from 'vitest';
import { Sidebar } from './Sidebar';

vi.mock('@/hooks/useDashboard', () => ({
  useDashboard: () => ({ data: { total_observables: 1482930, feeds_enabled: 11, total_feeds: 13 }, isLoading: false }),
}));
vi.mock('@/contexts/AuthContext', () => ({
  useAuth: () => ({ user: { username: 'areyes', role: 'admin' }, logout: vi.fn() }),
}));

describe('Sidebar', () => {
  it('renders brand nav with live counts and user', () => {
    render(<MemoryRouter><Sidebar /></MemoryRouter>);
    expect(screen.getByText('Dashboard')).toBeTruthy();
    expect(screen.getByText('1.48M')).toBeTruthy();
    expect(screen.getByText('11/13')).toBeTruthy();
    expect(screen.getByText(/api online/i)).toBeTruthy();
    expect(screen.getByText('admin')).toBeTruthy();
  });
});
```

- [ ] **Step 2: Run it (RED — current Sidebar has no counts/user).**
Run (in `frontend/`): `npm run test -- Sidebar` → FAIL.

- [ ] **Step 3: Implement** the Sidebar to the spec above. Match the screenshot for spacing/typography; use the named imports `import { SquaresFour, CrosshairSimple, Rss, GearSix, SignOut } from '@phosphor-icons/react'`. Guard the counts when `data` is undefined (render em dash). Keep `Sidebar` exported the same way (named `Sidebar`).

- [ ] **Step 4: Run it (GREEN).** `npm run test -- Sidebar` → PASS. Then `npm run build` clean.

- [ ] **Step 5: Commit**
```bash
git add src/components/layout/Sidebar.tsx src/components/layout/Sidebar.test.tsx
git commit -m "feat(layout): redesigned brand sidebar with live counts + user footer"
```

---

## Task 4: Redesigned Header / Topbar (with theme toggle)

**Files:**
- Modify: `src/components/layout/Header.tsx`
- Modify: `src/components/layout/AppLayout.tsx` (sticky topbar + 236px padding)
- Test: `src/components/layout/Header.test.tsx`

**Reference:** the top bar in the dashboard screenshots (title+subtitle left; search center-right with ⌘K; sun/moon toggle; crimson "Add Observable").

**Interfaces:**
- Consumes: `useTheme()` (`theme`, `toggle`), `useAuth()` (logout if still shown), `useLocation()` for title/subtitle.
- Produces: `<Header />` (props optional/back-compat; prefer hooks over props).

**Build to spec:**
- Sticky, ~60px, `bg-background/80 backdrop-blur`, border-bottom, z-30.
- Left: page title (16.5px/700) + subtitle (`text-muted-foreground`) from a `pathname → {title, subtitle}` map (Dashboard → "Aggregation overview & feed health"; add the other routes' titles too).
- Center-right: search input (`Input` primitive or styled) with a magnifier (`MagnifyingGlass`) and a `⌘K` hint chip on the right; pressing Enter routes to `/observables?q=<value>` (use `useNavigate`).
- Theme toggle: icon button — `Sun` when `theme==='dark'`, `Moon` when light — calls `toggle()`. `aria-label="Toggle theme"`.
- Primary button: crimson "Add Observable" (`Button` brand variant) with a `Plus` icon. (Wire its onClick to a no-op/route for now; the create-modal is an Observables-screen concern.)

- [ ] **Step 1: Write the failing test**

```tsx
// src/components/layout/Header.test.tsx
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, it, expect, vi } from 'vitest';
import { Header } from './Header';

const toggle = vi.fn();
vi.mock('@/contexts/ThemeContext', () => ({ useTheme: () => ({ theme: 'dark', toggle }) }));
vi.mock('@/contexts/AuthContext', () => ({ useAuth: () => ({ user: { username: 'a', role: 'admin' }, logout: vi.fn() }) }));

describe('Header', () => {
  it('shows the page title and toggles theme', () => {
    render(<MemoryRouter initialEntries={['/']}><Header /></MemoryRouter>);
    expect(screen.getByText('Dashboard')).toBeTruthy();
    fireEvent.click(screen.getByLabelText('Toggle theme'));
    expect(toggle).toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: RED.** `npm run test -- Header` → FAIL.
- [ ] **Step 3: Implement** Header to spec + update `AppLayout.tsx`: change `pl-60` to `pl-[236px]`, make the `<Header />` wrapper sticky, keep `<Outlet/>` in `<main className="mx-auto max-w-[1320px] p-6">`. If `App.tsx` passes `username`/`onLogout` props to `AppLayout`/`Header`, leave them working but have Header read `useAuth()`/`useTheme()` directly.
- [ ] **Step 4: GREEN.** `npm run test -- Header` → PASS; `npm run build` clean; existing tests still pass.
- [ ] **Step 5: Commit**
```bash
git add src/components/layout/Header.tsx src/components/layout/AppLayout.tsx src/components/layout/Header.test.tsx
git commit -m "feat(layout): sticky topbar with search, theme toggle, add-observable"
```

---

## Task 5: KPI cards row

**Files:**
- Create: `src/components/dashboard/KpiCards.tsx`
- Test: `src/components/dashboard/KpiCards.test.tsx`

**Reference:** the 4 cards in `screens/1-dashboard-dark.png`.

**Interfaces:**
- Consumes: `DashboardStats` (via prop `stats: DashboardStats`), and `compactNumber`/`vsAvgDelta` from `@/lib/dashboardFormat`.
- Produces: `<KpiCards stats={stats} />`.

**Build to spec (4 `Card`s, responsive 1/2/4 cols, gap-3.5):** each card = label (sans, muted, 13px) + a small colored icon tile (rounded, `color-mix` brand/categorical bg) top-right + big mono value (26px/800) + a subtitle/delta line.
1. **Total observables** — value `total_observables.toLocaleString()`; icon `CrosshairSimple` (brand). Subtitle: omit the delta (no historical data) — render nothing or a muted "indicators tracked".
2. **Active feeds** — value `\`${feeds_enabled} / ${total_feeds}\`` (mono); icon `Rss` (blue `cat-blue`). Subtitle: `\`${total_feeds - feeds_enabled} disabled\`` (muted) — derived, honest.
3. **Ingested (24h)** — value `last_24h_ingested.toLocaleString()`; icon `DownloadSimple` (green `cat-green`). Subtitle: if `vsAvgDelta(last_24h_ingested, daily_ingest_14d)` is non-null, show `\`▲ ${delta}% vs avg\`` green (or ▼ red if negative); else omit.
4. **Feed errors (24h)** — value `feed_errors_24h` (mono); icon `Warning` (`conf-critical`/red). Subtitle: if `feed_errors_24h > 0`, show the name of the first `feeds_health` item with `last_run_status === 'failure'` + " failed" (muted); else "all healthy".

- [ ] **Step 1: Write the failing test**

```tsx
// src/components/dashboard/KpiCards.test.tsx
import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { KpiCards } from './KpiCards';

const stats = {
  total_observables: 1482930, total_feeds: 13, feeds_enabled: 11,
  last_24h_ingested: 12408, feed_errors_24h: 1, by_type: {}, feeds_health: [
    { id: 'x', name: 'AbuseIPDB', enabled: true, last_run_status: 'failure', last_run_at: null, observable_count: 0 },
  ], confidence_distribution: { critical: 0, high: 0, medium: 0, low: 0 },
  daily_ingest_14d: Array.from({ length: 14 }, () => ({ date: '', count: 10000 })),
} as any;

describe('KpiCards', () => {
  it('renders the four KPIs with real values', () => {
    render(<KpiCards stats={stats} />);
    expect(screen.getByText('1,482,930')).toBeTruthy();
    expect(screen.getByText('11 / 13')).toBeTruthy();
    expect(screen.getByText('12,408')).toBeTruthy();
    expect(screen.getByText(/AbuseIPDB/)).toBeTruthy();   // failing-feed subtitle
  });
});
```

- [ ] **Step 2: RED.** `npm run test -- KpiCards` → FAIL.
- [ ] **Step 3: Implement** to spec. Phosphor imports: `CrosshairSimple, Rss, DownloadSimple, Warning`. Values use `font-mono`.
- [ ] **Step 4: GREEN** + `npm run build`.
- [ ] **Step 5: Commit** `feat(dashboard): KPI cards row`.

---

## Task 6: Ingestion trend chart

**Files:**
- Create: `src/components/dashboard/IngestionTrend.tsx`
- Test: `src/components/dashboard/IngestionTrend.test.tsx`

**Reference:** the "Ingestion volume" card (area+line, brand gradient) in the dashboard screenshots.

**Interfaces:**
- Consumes: `series: { date: string; count: number }[]` (the `daily_ingest_14d`).
- Produces: `<IngestionTrend series={series} />` — a `Card` titled "Ingestion volume" / subtitle "New observables per day · last 14 days", with the 14-day total (mono) and a recharts `AreaChart`.

**Build to spec:** recharts `<ResponsiveContainer>` + `<AreaChart data={series}>` with a brand `<Area type="monotone" dataKey="count" stroke="var(--brand)" fill="url(#grad)">` and a `<defs>` linearGradient from `var(--brand)` (opacity .35→0). Hide axes/grid for the compact sparkline look (or minimal). Tooltip optional. Title row shows `series.reduce(sum).toLocaleString()` as the total (mono).

> recharts + happy-dom: ResponsiveContainer needs a width — render the chart inside a `div` with an explicit height (e.g. `h-[180px]`); in the test, assert the title/total text rather than chart internals (charts don't lay out in happy-dom).

- [ ] **Step 1: Failing test** — render with a small series, assert "Ingestion volume" and the formatted total appear.
- [ ] **Step 2: RED.** `npm run test -- IngestionTrend`.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: GREEN** + `npm run build`.
- [ ] **Step 5: Commit** `feat(dashboard): 14-day ingestion area chart`.

---

## Task 7: Observable-types donut

**Files:**
- Create: `src/components/dashboard/TypeDonut.tsx`
- Test: `src/components/dashboard/TypeDonut.test.tsx`

**Reference:** the "Observable types" card (donut + center total + legend with %) in the screenshots.

**Interfaces:**
- Consumes: `byType: Record<string, number>`, `total: number`, plus `typeLabels`/`typeColors` (reuse the existing util the old `TypeBreakdown` used; if it lives in `@/lib/...`, import it — confirm the path).
- Produces: `<TypeDonut byType={byType} total={total} />` — `Card` "Observable types" / "By indicator class"; recharts `<PieChart>` donut (innerRadius for the hole) using categorical `cat-*` colors per type, center label showing `total.toLocaleString()` (mono) + "TYPES" small caps; a legend listing each type with a color dot, label, and `pct(count,total)%` (mono, right-aligned).

> Order types as in the screenshot: IP Address, URL, Domain, File Hash, Email, Command Line. Map type keys (`ip-addr`,`url`,`domain-name`,`file-hash`,`email-addr`,`command-line`) → labels/colors.

- [ ] **Step 1: Failing test** — render with a `byType` map, assert the legend shows the labels and at least one `%`.
- [ ] **Step 2: RED.** `npm run test -- TypeDonut`.
- [ ] **Step 3: Implement** (center label via an absolutely-positioned div over the chart, or a recharts `<Label>`).
- [ ] **Step 4: GREEN** + `npm run build`.
- [ ] **Step 5: Commit** `feat(dashboard): observable-types donut`.

---

## Task 8: Feed-status table

**Files:**
- Create: `src/components/dashboard/FeedStatusTable.tsx`
- Test: `src/components/dashboard/FeedStatusTable.test.tsx`

**Reference:** the feed-status table (status dot, name, type chip, mono count, last run, "View all") — lower-left card region of the dashboard (and the `RecentFeedRuns` it replaces).

**Interfaces:**
- Consumes: `feeds: FeedHealth[]`.
- Produces: `<FeedStatusTable feeds={feeds} />` — `Card` with header "Feed status" + a "View all" link (`react-router` `Link to="/feeds"`). Rows: status dot (green `cat-green` success / red `conf-critical` failed / pulsing blue `cat-blue` running via `animate-pulse-dot`), feed name, a small type chip (api/file/scraper — note `FeedHealth` may not carry `feed_type`; if absent, omit the chip or show status text), observable count (`compactNumber`, mono, right), last run relative time (reuse existing relative-time util if present; else `new Date(last_run_at).toLocaleDateString()`).

- [ ] **Step 1: Failing test** — render with two feeds (one success, one failure), assert names render and "View all" links to `/feeds`.
- [ ] **Step 2: RED.** `npm run test -- FeedStatusTable`.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: GREEN** + `npm run build`.
- [ ] **Step 5: Commit** `feat(dashboard): feed-status table`.

---

## Task 9: Confidence-distribution bars

**Files:**
- Create: `src/components/dashboard/ConfidenceBars.tsx`
- Test: `src/components/dashboard/ConfidenceBars.test.tsx`

**Reference:** the four labeled bars (Critical/High/Medium/Low with range, count, band-colored fill) — lower-right card region.

**Interfaces:**
- Consumes: `distribution: { critical: number; high: number; medium: number; low: number }`.
- Produces: `<ConfidenceBars distribution={distribution} />` — `Card` "Confidence distribution"; four rows, each: band label + range (Critical 80–100, High 60–79, Medium 40–59, Low 0–39), the count (mono, right), and a horizontal fill bar in the band color (`conf-critical`/`conf-high`/`conf-medium`/`conf-low`) sized to `count / max(counts)` width (track `bg-surface3`).

- [ ] **Step 1: Failing test** — render with counts `{critical:5,high:3,medium:2,low:1}`, assert all four labels + the counts render.
- [ ] **Step 2: RED.** `npm run test -- ConfidenceBars`.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: GREEN** + `npm run build`.
- [ ] **Step 5: Commit** `feat(dashboard): confidence-distribution bars`.

---

## Task 10: Assemble the Dashboard page

**Files:**
- Modify: `src/pages/DashboardPage.tsx`
- Delete usage of: `StatsGrid`, `TypeBreakdown`, `RecentFeedRuns` (leave the files; just stop importing them here — a later cleanup can remove them).
- Test: `src/pages/DashboardPage.test.tsx`

**Reference:** overall dashboard grid in `screens/1-dashboard-dark.png`.

**Interfaces:**
- Consumes: `useDashboard()`; the five components (`KpiCards`, `IngestionTrend`, `TypeDonut`, `FeedStatusTable`, `ConfidenceBars`).
- Produces: the composed page.

**Layout (per README):** `space-y-3.5`:
1. `<KpiCards stats={stats} />` (full width)
2. grid `lg:grid-cols-3 gap-3.5`: `<IngestionTrend series={stats.daily_ingest_14d}>` spans 2 cols, `<TypeDonut byType={stats.by_type} total={stats.total_observables}/>` 1 col.
3. grid `lg:grid-cols-3 gap-3.5`: `<FeedStatusTable feeds={stats.feeds_health}/>` spans 2 cols, `<ConfidenceBars distribution={stats.confidence_distribution}/>` 1 col.
Keep the existing loading/error handling from `useDashboard()`.

- [ ] **Step 1: Failing test**

```tsx
// src/pages/DashboardPage.test.tsx
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, it, expect, vi } from 'vitest';
import DashboardPage from './DashboardPage';

vi.mock('@/hooks/useDashboard', () => ({
  useDashboard: () => ({ isLoading: false, error: null, data: {
    total_observables: 1482930, total_feeds: 13, feeds_enabled: 11, last_24h_ingested: 12408,
    feed_errors_24h: 1, by_type: { 'ip-addr': 100 }, feeds_health: [],
    confidence_distribution: { critical: 1, high: 1, medium: 1, low: 1 },
    daily_ingest_14d: Array.from({ length: 14 }, (_, i) => ({ date: `d${i}`, count: 100 })),
  } }),
}));

describe('DashboardPage', () => {
  it('renders the redesigned sections', () => {
    render(<MemoryRouter><DashboardPage /></MemoryRouter>);
    expect(screen.getByText('1,482,930')).toBeTruthy();         // KPI
    expect(screen.getByText('Ingestion volume')).toBeTruthy();   // chart card
    expect(screen.getByText('Observable types')).toBeTruthy();   // donut card
    expect(screen.getByText('Confidence distribution')).toBeTruthy();
  });
});
```

- [ ] **Step 2: RED.** `npm run test -- DashboardPage`.
- [ ] **Step 3: Implement** the assembly.
- [ ] **Step 4: GREEN** + full `npm run test` + `npm run build` clean.
- [ ] **Step 5: Commit** `feat(dashboard): assemble redesigned dashboard page`.

---

## Final verification
- [ ] `uv run --extra dev pytest` → all green (20 incl. the new series test).
- [ ] `cd frontend && npm run test` → all green; `npm run build` clean.
- [ ] Manual: `COMPOSE_PROJECT_NAME=emergentcti docker compose up --build -d` from the worktree, open http://localhost:8080 — sidebar/topbar/dashboard match `screens/1-dashboard-dark.png`; theme toggle flips dark/light and persists.

## Self-Review
- **Coverage:** layout (Sidebar T3, Header/topbar+toggle T4, AppLayout T4); KPIs T5; ingestion chart T1+T2+T6; donut T7; feed table T8; confidence bars T9; assembly T10. Every screenshot region maps to a task.
- **No fabricated data:** WoW total delta omitted (no source); "vs avg" derived from `daily_ingest_14d`; feed-error subtitle from `feeds_health`. Documented in Global Constraints.
- **Type consistency:** `daily_ingest_14d: {date,count}[]` identical in backend response (T1), type (T2), chart (T6), page (T10). `compactNumber/pct/vsAvgDelta` signatures used as defined in T2.
- **Open item for implementers:** confirm the real paths of the existing `typeLabels`/`typeColors` and any relative-time helper (used by `TypeBreakdown`/`RecentFeedRuns` today) and reuse them in T7/T8 rather than duplicating.
