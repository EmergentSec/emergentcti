# Dependency audit

`scripts/audit-deps.sh` is the single, repeatable dependency audit for EmergentCTI. It
runs locally and in CI (`.github/workflows/dependency-audit.yml`) with the same policy.
It was introduced for issue #18.

## Running it locally

Requirements: `npm` (Node 20+), `uv`, `python3`, and
[`osv-scanner`](https://github.com/google/osv-scanner) v2 on `PATH`. CI pins
osv-scanner 2.7.0 and verifies its checksum. The audit needs network access to the npm
registry and `api.osv.dev`. No `node_modules` or virtualenv is needed: both scanners
read the lockfiles.

```bash
scripts/audit-deps.sh            # prints a summary table and the findings, then exits 0, 1 or 2
AUDIT_OUTPUT_DIR=out scripts/audit-deps.sh   # also keep the raw scanner JSON in ./out
```

Example summary:

```
scope    source     crit high  mod  low  unk  exc  fails on  result
-------------------------------------------------------------------
runtime  frontend      0   14   27    1    0    0  high      FAIL
runtime  backend       0    0    0    0    0    0  high      clean
tooling  frontend      0   11   15    3    0    0  critical  report
tooling  backend       0    0    0    0    0    0  critical  clean
```

Counts are **advisory × package** pairs. `npm audit`'s own `metadata.vulnerabilities`
counts vulnerable *packages*, so it reports smaller numbers for the same data. For
example, one axios version with 13 high advisories is 1 package to npm and 13 rows
here. `exc` counts findings suppressed by a valid exception.

## Scopes

| Scope | Frontend | Backend |
|---|---|---|
| **runtime**: shipped in the nginx bundle or the API image | `npm audit --omit=dev` on `frontend/package-lock.json` | osv-scanner on `uv export --frozen --no-dev` (what the Docker image installs) |
| **tooling**: build, test and lint only | `npm audit` (full tree) minus runtime findings | osv-scanner on `uv export --frozen --extra dev` minus runtime findings |

A finding reported as runtime never appears again under tooling. "Tooling" does not
mean "safe": build tooling processes our source and runs on developer machines and CI.
It gets a higher failure threshold, but it is still reported.

### Why osv-scanner for the backend

pip-audit was considered. Its JSON output has **no severity**, so a "fail on
high/critical" policy could not be applied. osv-scanner reports a `max_severity` (CVSS)
per advisory group, merges PYSEC/GHSA/CVE aliases into one finding, and reads the
exported requirements directly. It runs with `--no-resolve` because the export is
already the complete pinned closure, and resolving again would add another network
dependency. During the first audit, pip-audit was run once as a cross-check and agreed
(see `docs/security/2026-11-backend-audit.md`).

## Severity policy

| Scope | Fails the run (exit 1) | Reported only |
|---|---|---|
| runtime | high, critical | moderate, low |
| tooling | critical | high, moderate, low |

Thresholds are configurable. The defaults are shown:

| Variable | Default | Meaning |
|---|---|---|
| `AUDIT_RUNTIME_FAIL_LEVEL` | `high` | lowest runtime severity that fails (`low`, `moderate`, `high`, `critical`, `none`) |
| `AUDIT_TOOLING_FAIL_LEVEL` | `critical` | the same for tooling |
| `AUDIT_UNKNOWN_SEVERITY` | `high` | severity assumed when an advisory has none. This fails closed: an unscored advisory is treated as high, not ignored |
| `AUDIT_EXCEPTIONS_FILE` | `security/audit-exceptions.json` | exceptions file |
| `AUDIT_EXCEPTION_MAX_DAYS` | `90` | longest allowed exception lifetime, counted from today |
| `AUDIT_OUTPUT_DIR` | temporary directory | keep the raw scanner JSON |

Changing a threshold in CI is a policy change and needs review like any other code
change.

## Exit codes

| Code | Meaning |
|---|---|
| `0` | Clean per policy. Findings below the thresholds may still be listed. |
| `1` | Policy violation: a finding at or above a scope's fail level, an **expired** exception, or an exception that expires more than 90 days out. |
| `2` | **The audit could not be completed.** A scanner failed, the registry or `api.osv.dev` was unreachable, output was missing or malformed, a required tool is missing, or the configuration or exceptions file is invalid. This is never a clean result. |

If one scope fails to scan and another has violations, the exit code is 2, and the
violations are still printed. An incomplete audit is never reported as if it were
complete.

How failures are detected:

- `npm audit` exits 1 both when it finds vulnerabilities and when the request fails.
  So the script checks the JSON: an `error` key, or missing `metadata.vulnerabilities`,
  means failure.
- osv-scanner prints a valid, **empty** `{"results": []}` when `api.osv.dev` is
  unreachable, and signals the failure only with exit code 127. Only exit codes 0
  (clean) and 1 (vulnerabilities) are accepted. Results that contradict the exit code
  are also treated as failures.
- Any unexpected error in the wrapper or evaluator (an ERR trap, a crash) maps to 2,
  never to 1 or 0.

## Exceptions

Fix the finding where possible. If a fixable high or critical runtime finding cannot be
fixed yet, add an entry to `security/audit-exceptions.json` (a JSON array):

```json
[
  {
    "id": "GHSA-xxxx-xxxx-xxxx",
    "package": "example-pkg",
    "scope": "runtime",
    "severity": "high",
    "reason": "Why it is not exploitable here / why it cannot be fixed yet (be specific: code path, config).",
    "mitigation": "What reduces the risk meanwhile, and the follow-up issue that removes this entry.",
    "owner": "person or team accountable for the follow-up",
    "expires": "2027-01-31"
  }
]
```

Rules, enforced by the script unless marked as review-only:

- **Narrow.** An exception suppresses only the finding with that exact advisory `id`
  (GHSA, CVE or PYSEC; any alias of the finding matches), that `package`, and that
  `scope`. A runtime exception does not cover the same advisory in tooling, and vice
  versa. There are no wildcards or package-wide suppressions.
- **Complete.** All eight fields are required and must be non-empty. `scope` must be
  `runtime` or `tooling`, and `expires` must be in `YYYY-MM-DD` format.
- **Time-bounded.** `expires` may be at most 90 days out. On and after the day following
  `expires`, the exception stops suppressing and the run fails with `exception EXPIRED`.
  The run fails even if the finding has gone, which forces the stale entry to be
  removed.
- **Justified** (review-only). `reason` must say why the vulnerable code is not
  reachable or why it cannot be fixed yet. "Transitive dependency" alone is not a
  reason. `mitigation` should link the follow-up issue.
- Exceptions that match nothing are listed as a `note:`, so they can be cleaned up.
- Adding, extending or renewing an exception goes through normal PR review. Renewing
  needs a fresh justification, not just a new date.

## CI behaviour

`.github/workflows/dependency-audit.yml` runs on every pull request, on pushes to
`main`, weekly (Monday 06:17 UTC, so new advisories against unchanged lockfiles still
surface), and on demand (`workflow_dispatch`). It has `permissions: contents: read`, and
every action is pinned to a full commit SHA.

| Job | What it does |
|---|---|
| `audit` | Installs the pinned, checksum-verified osv-scanner, then runs `scripts/audit-deps.sh`. Exit 1 **and exit 2 both fail the job**; there is no `continue-on-error`. The summary table goes to the job summary, and the raw scanner JSON is uploaded as the `dependency-audit` artifact. |
| `frontend` | `npm ci && npm test && npm run build` on Node 20 (lockfile must match `package.json`). |
| `backend` | `uv lock --check`, `uv sync --locked --extra dev`, then `pytest` on Python 3.12 (the image's version). |

A failing scheduled run means a new advisory affects code already on `main`. Triage it
like a failing PR: upgrade, or add a justified, time-bounded exception.

## Backend lockfile

`uv.lock` is committed, and the Docker image installs with `uv sync --locked`. The image
build fails if the lockfile is missing or out of date with `pyproject.toml`. To change
backend dependencies:

```bash
uv lock --upgrade-package <pkg>   # targeted upgrade within pyproject constraints
uv lock --check                   # what CI runs
scripts/audit-deps.sh
```

## Tests

The policy and wrapper logic is tested offline in `tests/test_audit_deps.py`, using
fixture JSON and fake scanners on `PATH`:

```bash
uv run --extra dev pytest tests/test_audit_deps.py
```
