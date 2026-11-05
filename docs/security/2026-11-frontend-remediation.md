# Frontend dependency remediation (November 2026)

Issue: [EmergentSec/emergentcti#18](https://github.com/EmergentSec/emergentcti/issues/18)

Evidence JSON (machine-readable):

| Phase | Runtime (`--omit=dev`) | Full tree |
| --- | --- | --- |
| Before | `docs/security/evidence/2026-11-frontend-before-runtime.json` | `docs/security/evidence/2026-11-frontend-before-full.json` |
| After | `docs/security/evidence/2026-11-frontend-after-runtime.json` | `docs/security/evidence/2026-11-frontend-after-full.json` |

Counts below are from those files at remediation time; they are **not** a live audit — re-run `npm audit` to get current results.

## Summary counts

| Audit scope | Before (high / moderate / total) | After (high / moderate / total) |
| --- | --- | --- |
| Runtime (`npm audit --omit=dev`) | 2 / 4 / 6 | **0** / 2 / 2 |
| Full (`npm audit`) | 10 / 9 / 20 | 1 / 3 / 4 |

All **runtime high** findings were resolved. Remaining items are moderate (runtime router) or dev-tooling-only (Vite dev server / esbuild).

## Remediated packages

| Package | Scope | Severity (before) | Advisory IDs | Locked before → after | Fixed in | Reachability (before fix) |
| --- | --- | --- | --- | --- | --- | --- |
| `axios` | runtime | high (+ nested moderate/low) | GHSA-pmwg-cvhr-8vh7, GHSA-3p68-rc4w-qgx5, GHSA-w9j2-pvgh-6h63, GHSA-3w6x-2g7m-8v23, GHSA-xhjh-pmcv-23jw, GHSA-445q-vr5w-6q77, … (see before JSON) | 1.13.4 → **1.21.0** | axios ≥1.20.0 | **Browser bundle:** `frontend/src/api/client.ts` uses `axios.create` with JSON + cookies; Vite resolves the **XHR adapter**, not the Node HTTP adapter. Node-only paths (NO_PROXY/SSRF, `formDataToStream`, redirect agent, etc.) are **not shipped** in the production static bundle but were still upgraded because the package is a direct runtime dependency. |
| `form-data` | runtime (transitive) | high | GHSA-hmw2-7cc7-3qxx | 4.0.5 → **4.0.6** | form-data ≥4.0.6 | Transitive via axios; **not used** in browser builds (Node multipart stack). Fixed by axios 1.21.0 lock resolution. |
| `follow-redirects` | runtime (transitive) | moderate | GHSA-r4q5-vmmm-2653 | 1.15.11 → **1.16.2** | follow-redirects ≥1.16.0 | Transitive via axios Node adapter only; **not in browser bundle**. Fixed via axios upgrade. |
| `@remix-run/router` | runtime (transitive) | moderate | GHSA-2j2x-hqr9-3h42 | 1.23.2 → **1.23.4** | @remix-run/router ≥1.23.3 | **Reachable:** SPA uses `BrowserRouter`, `Link`, `useNavigate`, deep links (`/reports/:id`, etc.). Same-origin open-redirect class; app uses app-controlled path templates, not raw user URLs in `to=`. |
| `react-router` / `react-router-dom` | runtime | moderate | GHSA-2j2x-hqr9-3h42 (router), plus react-router-dom chain | 6.30.3 → **6.30.6** | react-router-dom 6.30.6 | **Reachable** for client-side routing across the app (`App.tsx`, layout, entity pages). |
| `happy-dom` | tooling | high | GHSA-834v-8h66-3h79, GHSA-c8p4-j97h-3vg8, GHSA-5fpq-26gf-qwcr | 20.10.2 → **21.0.4** | happy-dom ≥21.0.4 | Test environment only (`vitest`); not in production image runtime. |
| `postcss` | tooling | high | GHSA-fxqj-rqcc-2cmp, GHSA-r28c-9q8g-f849 | 8.4.49 → **8.5.32** | postcss ≥8.5.23 | Build-time CSS pipeline only. |
| `vite` | tooling | high (aggregate) | GHSA-4w7w-66w2-5vf9, GHSA-v6wh-96g9-6wx3, GHSA-698v-4r3x-3vcv, GHSA-r825-w8mm-5pxw, GHSA-587h-7wmj-h5pm, … | 5.4.11 → **5.4.21** | Partial; see remaining | **Dev/preview server only** in this repo; production Docker stage serves static `dist/` via nginx. |
| `vitest` | tooling | moderate | GHSA-82fw-gwwq-j7x9 | 4.1.8 → **4.1.12** | vitest ≥4.1.11 | CI/local tests only. |
| `rollup` | tooling | high | GHSA-mw96-cpmx-2vgc | 4.58.0 → **4.67.5** | rollup ≥4.59.0 | Via `npm audit fix` (build dependency of Vite). Build-time only. |
| `@babel/core` | tooling | low | GHSA-4x5r-pxfx-6jf8 | 7.29.0 → **7.29.13** | @babel/core ≥7.29.1 | Via `npm audit fix`; compile-time only. |
| `browserslist` | tooling | high | GHSA-c83g-rgw3-j3cx, GHSA-73wf-gq98-2v4g | 4.28.0 → **4.29.5** | browserslist ≥4.28.7 | Build tooling; not in browser bundle. |
| `picomatch` | tooling | high | GHSA-3v7f-55p6-f55p, GHSA-c2c7-rcm5-vvqj | 2.3.1 → **4.0.7** (nested) | picomatch ≥4.0.3 | Transitive dev tooling; not in production bundle. |
| `postcss-selector-parser` | tooling | moderate | GHSA-w9m9-85wc-3x92, GHSA-rj75-hqrm-r3gf | 6.1.2 → **6.1.5** | ≥6.1.5 | Tailwind/postcss build chain only. |
| `nanoid` | tooling | high | GHSA-28wg-ghj8-5hjv, GHSA-2v37-7h3g-55p8 | 3.3.11 → **3.3.20** | nanoid ≥3.3.11 patched line | Dev/build transitive; not runtime. |
| `source-map-js` | tooling | high | GHSA-68fv-2mgg-jv7q | 1.2.1 → **1.2.2** | source-map-js ≥1.2.2 | Build tooling only. |
| `baseline-browser-mapping` | tooling | moderate | GHSA-w5vr-8v7q-w6rv | 2.8.19 → **2.11.35** | ≥2.11.0 | Dev transitive; fixed via `npm audit fix`. |

### `package.json` overrides

```json
"overrides": {
  "vitest": {
    "vite": "$vite"
  }
}
```

**Justification:** `npm audit fix` introduced a nested `vitest → vite@8` peer resolution that broke `npm ci` under npm 10 (Node 20 Alpine Docker builder) and would have been an undeclared major Vite bump. The override pins Vitest’s nested Vite to the project’s direct `vite@5.4.21` devDependency.

### `npm audit fix` (non-force)

Reviewed lockfile diff: patch/minor bumps only for Babel, browserslist, baseline-browser-mapping, picomatch, postcss-selector-parser, rollup, nanoid, source-map-js, and related transitive packages. No changes to direct runtime semver ranges beyond the intentional `npm install` upgrades above.

## Remaining findings

| Component | Scope | Severity | Advisory IDs | Rationale | Mitigation | Follow-up |
| --- | --- | --- | --- | --- | --- | --- |
| `react-router` / `react-router-dom` | runtime | moderate | GHSA-wrjc-x8rr-h8h6, GHSA-337j-9hxr-rhxg | npm reports fix only on **React Router v7**; issue scope forbids v7 migration here. | Client-only SPA (no SSR hydration); navigation uses internal path templates; validate IDs from API. Monitor React Router 6.x security releases. | Dedicated issue: evaluate React Router 7 migration or upstream 6.x backports. |
| `vite` | tooling | high (scanner aggregate) | GHSA-587h-7wmj-h5pm, GHSA-698v-4r3x-3vcv, GHSA-r825-w8mm-5pxw, GHSA-rq7h-c2jc-7f22, GHSA-fx2h-pf6j-xcff, … | Patched floor is **>6.4.3** / Vite 8; staying on **Vite 5.4.x** per issue boundary. | Production deploy serves static assets; do not expose Vite dev server to untrusted networks; use `npm run build` in CI/Docker only. | Plan Vite 6+ upgrade track (separate from #18). |
| `esbuild` (via Vite 5) | tooling | moderate | GHSA-67mh-4wv8-2f99 | Bundled with Vite 5 (`esbuild@0.21.5`); fix requires newer Vite major. | Dev-server exposure control; no esbuild in nginx runtime image. | Same Vite upgrade track. |

## Proposed time-bounded exceptions (≤90 days)

| id | package | scope | severity | reason | mitigation | owner | expires |
| --- | --- | --- | --- | --- | --- | --- | --- |
| EX-2026-11-FE-001 | react-router / react-router-dom | runtime | moderate | Fix requires React Router v7; out of scope for #18 | SPA-only; controlled routes; no SSR `deserializeErrors` path | frontend | 2026-02-03 |
| EX-2026-11-FE-002 | vite | tooling | high | Vite 5.x line capped; advisories require ≥6.4.4 | Static nginx deploy; restrict dev/preview servers | frontend | 2026-02-03 |
| EX-2026-11-FE-003 | esbuild | tooling | moderate | Transitive of pinned Vite 5 | Dev network isolation; not in production runtime | frontend | 2026-02-03 |

## Verification (2026-11-05)

Commands run from `frontend/` after final lockfile (regenerated with **npm 10** inside `node:20-alpine` so Docker `npm ci` matches CI):

| Command | Result |
| --- | --- |
| `rm -rf node_modules && npm ci` | exit 0 |
| `npm test` | exit 0 — 75 files, 683 tests passed |
| `npm run build` | exit 0 — `tsc -b && vite build` |
| `npm audit --omit=dev` | exit 1 (moderate only) — **0 high**, 2 moderate (`react-router` chain) |
| `docker build -t emergentcti-frontend:a18 frontend` | exit 0 (via `newgrp docker`) |

Dockerfile change: `npm install` → **`npm ci`**, require `package-lock.json` (no glob).

## React Router API surface (reachability notes)

Used APIs include: `BrowserRouter`, `Routes`, `Route`, `Navigate`, `Link`, `NavLink`, `Outlet`, `useNavigate`, `useParams`, `useSearchParams`, `useLocation`, `MemoryRouter` (tests). No React Router data APIs or SSR loaders in this codebase.
