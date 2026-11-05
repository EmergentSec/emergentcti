# Backend dependency audit, November 2026 (issue #18)

Audit date: 2026-11-05. Scope: the Python backend (`pyproject.toml` / `uv.lock`). The
frontend is covered separately in `docs/security/2026-11-frontend-remediation.md`. The
process and policy are described in [dependency-audit.md](dependency-audit.md).

## Starting point: nothing was locked

Before this change the backend had **no lockfile**:

- `pyproject.toml` used only open-ended `>=` constraints.
- `uv.lock` was listed in `.gitignore`.
- The Dockerfile copied `uv.lock*` (optional) and ran `uv sync --no-dev` with no
  `--locked`, and pulled `ghcr.io/astral-sh/uv:latest`.

As a result, every image build installed whatever was newest on PyPI at build time.
There was no fixed dependency set to audit, and two builds of the same commit could
ship different code. For the same reason, **images built before this change cannot be
audited from the repository**. They may contain older versions than those below, so
rebuild and redeploy them from a commit that includes `uv.lock`.

Changes:

- `uv lock` produced `uv.lock`: 64 packages for Python ≥ 3.12, counting the project itself. `pyproject.toml`
  constraints are **unchanged**, because no finding required raising one.
- `uv.lock` was removed from `.gitignore` and committed.
- The Dockerfile now copies `uv.lock` without a wildcard (the build fails if it is
  missing) and runs `uv sync --locked` in both sync steps (the build fails if the lock
  is stale). The uv image is pinned to `0.13.4`.

## Method

The locked sets were exported from `uv.lock` and scanned:

| Scope | Export | Packages |
|---|---|---|
| runtime (what the image installs) | `uv export --frozen --no-dev --no-hashes --no-emit-project` | 48 |
| tooling (`[dev]` extra: pytest, pytest-asyncio, pytest-httpx, aiosqlite, ruff, mypy and their dependencies) | `uv export --frozen --extra dev ...` minus runtime | 15 |

Scanners:

- **osv-scanner 2.7.0**, the primary scanner and the one used by `scripts/audit-deps.sh`:
  `osv-scanner scan source --no-resolve --format json -L requirements.txt:<export>`. It
  queries OSV, which aggregates the PyPA advisory database (PYSEC), GitHub advisories
  (GHSA) and CVE aliases.
- **pip-audit 2.10.1**, run once as a cross-check:
  `pip-audit -r <export> --no-deps --disable-pip -f json`.

Before trusting an empty result, we confirmed that osv-scanner detects known
vulnerabilities in this mode. A probe file pinning `jinja2==2.10` and `pyjwt==1.5.0`
returned 6 and 13 advisory groups, with CVSS-derived severities. We also confirmed that
an unreachable `api.osv.dev` produces exit 127, not a clean result.

Raw evidence: [`evidence/2026-11-backend-before.json`](evidence/2026-11-backend-before.json).
It contains both exports, the osv-scanner JSON for both scopes, the pip-audit results,
the scanner versions, the base commit and the SHA-256 of `uv.lock`.

## Findings: before

| Scope | osv-scanner | pip-audit |
|---|---|---|
| runtime (48 packages) | **0** | **0** |
| tooling (15 packages) | **0** | **0** |

There are no advisory IDs to report: no PYSEC, GHSA or CVE entry matches any locked
version.

Notable locked runtime versions, for reference when future advisories are published:
fastapi 0.162.0, starlette 1.10.0, uvicorn 0.54.0, gunicorn 26.2.0, sqlalchemy 2.1.8,
psycopg 3.3.8, alembic 1.20.1, pydantic 2.14.3, httpx 0.28.1, h11 0.16.0,
cryptography 50.0.2, pyjwt 2.15.1, bcrypt 5.0.0, python-multipart 0.0.33, lxml 6.1.3,
beautifulsoup4 4.15.0, redis 8.1.0, apscheduler 3.11.3. The full list is in the evidence
file.

## Upgrades and after

**No upgrades were needed**, so there are no `uv lock --upgrade-package` changes and no
version changes beyond creating the lock itself. The after state is the same as the
before state (0 findings in either scope), so no separate after evidence file was
recorded. `scripts/audit-deps.sh` reports the backend as `clean` in both scopes.

## Reachability and exposure

There are no current findings to assess. These packages handle untrusted input in this
deployment, so a future advisory against any of them should be treated as reachable
until shown otherwise:

| Package | Untrusted input |
|---|---|
| starlette, fastapi, python-multipart, h11, uvicorn, gunicorn | HTTP requests from API clients, including form and multipart parsing |
| lxml, beautifulsoup4 | HTML/XML from external threat-intel feeds |
| httpx | outbound requests to feed URLs and AI providers, including redirects and proxies |
| pyjwt, bcrypt, cryptography | authentication tokens, password hashes, secret encryption |
| croniter, apscheduler | administrator-provided schedule expressions |

Tooling packages (pytest, ruff, mypy and others) are not installed in the production
image (`uv sync --no-dev`; the `[dev]` extra is never requested there). They run only
in development and CI.

## Remaining and follow-up

- No accepted risks or exceptions for the backend, and `security/audit-exceptions.json`
  has no backend entries.
- New advisories against these pins will fail the weekly CI audit (runtime high or
  critical) or appear in its report (tooling).
- Rebuild and redeploy any backend image built before `uv.lock` existed (see the
  starting point section).
