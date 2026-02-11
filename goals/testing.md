# Testing -- Run Tests and Validate Changes

## Objective

Validate all code changes through a multi-layer testing strategy covering unit tests, integration tests, linting, type checking, and security scanning. No feature should be merged without passing the full test pipeline.

---

## Backend Testing

### Test Framework

- **Runner:** pytest with async support (pytest-asyncio)
- **Database:** SQLite in-memory for test isolation (no PostgreSQL dependency in CI)
- **Fixtures:** Defined in `tests/conftest.py` for database sessions, test clients, and auth tokens

### Running Tests

```bash
# Run all backend tests
uv run pytest

# Run with verbose output
uv run pytest -v

# Run a specific test file
uv run pytest tests/test_observables.py -v

# Run a specific test function
uv run pytest tests/test_observables.py::test_create_observable -v

# Run with coverage report
uv run pytest --cov=src/cti --cov-report=term-missing

# Run only tests matching a keyword
uv run pytest -k "feed" -v
```

### Test Organization

```
tests/
  conftest.py                 # Shared fixtures (db session, client, auth)
  test_observables.py         # Observable CRUD and validation
  test_feeds.py               # Feed management and ingestion
  test_enrichment.py          # Enrichment pipeline
  test_auth.py                # Authentication and authorization
  test_search.py              # Search and correlation
  test_alerts.py              # Alert rules and notifications
  test_attack.py              # MITRE ATT&CK mapping
  test_relationships.py       # Observable relationships
  test_campaigns.py           # Campaign management
  test_threat_actors.py       # Threat actor tracking
  test_confidence.py          # Confidence scoring logic
  test_export.py              # STIX/CSV export
  test_import.py              # STIX/CSV import
```

### Writing Tests

```python
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_create_observable(client: AsyncClient, auth_headers: dict):
    response = await client.post(
        "/api/v1/observables",
        json={
            "type": "ip-addr",
            "value": "192.168.1.1",
            "confidence_score": 75,
        },
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["type"] == "ip-addr"
    assert data["value"] == "192.168.1.1"
    assert data["confidence_score"] == 75
```

---

## Frontend Testing

### TypeScript Type Checking

```bash
cd frontend && npx tsc --noEmit
```

This validates all TypeScript types without producing output files. Fix any type errors before proceeding.

### Build Validation

```bash
cd frontend && npx vite build
```

A successful build confirms that all imports resolve, JSX compiles, and no syntax errors exist.

### Linting

```bash
cd frontend && npx eslint src/
```

---

## Linting (Backend)

### Ruff Linter

```bash
# Check for lint errors
uv run ruff check .

# Auto-fix safe fixes
uv run ruff check --fix .

# Check formatting
uv run ruff format --check .

# Apply formatting
uv run ruff format .
```

Ruff is configured in `pyproject.toml` under `[tool.ruff]`. Key rules enforced:
- Import sorting (isort-compatible)
- Unused imports and variables
- PEP 8 style compliance
- Type annotation style consistency

---

## Type Checking (Backend)

### Mypy

```bash
uv run mypy src/
```

Mypy configuration is in `pyproject.toml` under `[tool.mypy]`. Key settings:
- `strict = false` (not all code is fully typed yet)
- `check_untyped_defs = true`
- SQLAlchemy plugin enabled for ORM type inference

---

## Security Testing

### SAST with Bandit

```bash
uv run bandit -r src/ -c pyproject.toml
```

Bandit scans for common Python security issues:
- Hardcoded passwords
- SQL injection risks
- Insecure use of `eval()` or `exec()`
- Weak cryptographic practices

### Dependency Audit (Python)

```bash
uv run pip-audit
```

Checks all installed packages against known vulnerability databases (OSV, PyPI advisory).

### Dependency Audit (Frontend)

```bash
cd frontend && npm audit
```

Checks npm packages for known vulnerabilities.

### Container Scanning

```bash
# Scan Docker images with Trivy
trivy image cti-api:latest
trivy image cti-frontend:latest
```

### Secrets Detection

```bash
# Scan repository for leaked secrets
trufflehog filesystem --directory=. --exclude-paths=.gitignore
```

---

## CI Pipeline

### GitHub Actions Workflows

Three CI workflows are configured:

#### `.github/workflows/ci.yml` -- Primary CI

Triggers: push to main, pull requests

Steps:
1. Checkout code
2. Set up Python 3.12 + uv
3. `uv sync` to install dependencies
4. `uv run ruff check .` -- lint
5. `uv run ruff format --check .` -- format check
6. `uv run pytest --cov=src/cti` -- tests with coverage
7. Upload coverage report

#### `.github/workflows/security.yml` -- Security Scanning

Triggers: push to main, weekly schedule

Steps:
1. `uv run bandit -r src/ -c pyproject.toml` -- SAST
2. `uv run pip-audit` -- Python dependency audit
3. `cd frontend && npm audit` -- Frontend dependency audit
4. Trivy container scan (if Docker image built)

#### `.github/workflows/build.yml` -- Docker Build

Triggers: push to main, tags

Steps:
1. Build Docker images for api, worker, frontend
2. Run Trivy scan on built images
3. Push to registry (on tag)

---

## Pre-Merge Checklist

Before merging any feature branch:

```
[ ] uv run pytest                          -- All tests pass
[ ] uv run ruff check .                    -- No lint errors
[ ] uv run ruff format --check .           -- Code is formatted
[ ] uv run mypy src/                       -- No type errors
[ ] cd frontend && npx tsc --noEmit        -- Frontend types valid
[ ] cd frontend && npx vite build          -- Frontend builds
[ ] uv run bandit -r src/ -c pyproject.toml -- No security issues
[ ] uv run pip-audit                       -- No vulnerable dependencies
[ ] New migrations tested (upgrade + downgrade)
[ ] API docs updated (if new endpoints)
```

---

## Debugging Failed Tests

### Common Issues

| Problem | Solution |
|---------|----------|
| `ModuleNotFoundError` | Run `uv sync` to install dependencies |
| Database schema mismatch | Delete test DB, re-run (SQLite in-memory auto-recreates) |
| Async test hanging | Ensure `@pytest.mark.asyncio` decorator is present |
| Auth test failing | Check that test fixtures create admin user correctly |
| Elasticsearch test failing | Tests use mocked ES client; check mock setup |

### Verbose Debug Output

```bash
# Maximum verbosity with print output
uv run pytest -vvs tests/test_specific.py

# Show local variables on failure
uv run pytest --tb=long
```

---

## Tools

| Tool | Purpose |
|------|---------|
| `tools/test/run_tests.sh` | Run full backend test suite with coverage |
| `tools/test/lint_check.sh` | Run ruff lint + format check |
| `tools/security/scan.sh` | Run Bandit, pip-audit, npm audit |

---

## Related Files

- **Test config:** `pyproject.toml` (pytest, ruff, mypy, bandit sections)
- **Test fixtures:** `tests/conftest.py`
- **CI:** `.github/workflows/ci.yml`, `security.yml`, `build.yml`
- **Context:** `context/observable_types.md` (validation rules for test data)
