# Security Audit -- Security Scanning and Hardening

## Objective

Perform comprehensive security auditing of the EmergentCTI platform covering static analysis, dependency vulnerabilities, container security, secrets management, and compliance with OWASP Top 10 guidelines. This goal defines the full security posture assessment and hardening workflow.

---

## Static Application Security Testing (SAST)

### Bandit -- Python SAST

```bash
uv run bandit -r src/ -c pyproject.toml
```

Bandit checks for:
- Hardcoded passwords and secret keys (B105, B106, B107)
- SQL injection via string formatting (B608)
- Use of `eval()`, `exec()`, `pickle` (B301, B307, B102)
- Insecure use of `subprocess` (B603, B607)
- Weak cryptographic algorithms (B303, B304)
- Insecure TLS/SSL settings (B502, B503)

#### Bandit Configuration

In `pyproject.toml`:
```toml
[tool.bandit]
exclude_dirs = ["tests", ".venv"]
skips = []
```

#### Handling False Positives

If Bandit flags legitimate code (e.g., test fixtures with dummy passwords), add a `# nosec` comment with a justification:
```python
test_password = "test-only-password"  # nosec B105 - test fixture, not production
```

---

## Dependency Auditing

### Python Dependencies

```bash
uv run pip-audit
```

pip-audit checks all installed packages against:
- OSV (Open Source Vulnerability) database
- PyPI advisory database

#### Handling Vulnerabilities

1. Check if a patched version exists: `uv add package==fixed_version`
2. If no fix exists, evaluate risk and document in `SECURITY.md`
3. For transitive dependencies, check if the parent package has an update

### Frontend Dependencies

```bash
cd frontend && npm audit
```

#### Auto-Fix

```bash
cd frontend && npm audit fix
```

For breaking changes:
```bash
cd frontend && npm audit fix --force  # Use with caution
```

---

## Container Scanning

### Trivy -- Image Vulnerability Scanner

```bash
# Build images first
docker compose build

# Scan API image
trivy image cti-api:latest --severity HIGH,CRITICAL

# Scan Frontend image
trivy image cti-frontend:latest --severity HIGH,CRITICAL

# Scan with JSON output for CI
trivy image cti-api:latest --format json --output trivy-report.json
```

### Dockerfile Best Practices

- Use specific image tags (not `:latest` in production)
- Run as non-root user
- Multi-stage builds to minimize image size
- Do not copy `.env` or secrets into images
- Use `.dockerignore` to exclude sensitive files

---

## Secrets Detection

### TruffleHog

```bash
# Scan repository for leaked secrets
trufflehog filesystem --directory=. --exclude-paths=.gitignore

# Scan git history
trufflehog git file://. --since-commit HEAD~50
```

### What to Check

- API keys committed to git history
- Database passwords in code or config files
- JWT secrets in source code
- Fernet encryption keys in plaintext
- OAuth client secrets

### Secret Management in EmergentCTI

All secrets are handled through environment variables and encryption:

| Secret | Storage | Access |
|--------|---------|--------|
| `SECRET_KEY` | `.env` (not committed) | `Settings.SECRET_KEY` |
| `POSTGRES_PASSWORD` | `.env` | `Settings.POSTGRES_PASSWORD` |
| `FEED_ENCRYPTION_KEY` | `.env` | Fernet key for feed auth encryption |
| Feed API keys | `feeds.auth_config_encrypted` column | Fernet decrypted at runtime |
| Enrichment API keys | `enrichment_configs.api_key_encrypted` column | Fernet decrypted at runtime |
| SSO client secrets | `.env` | `Settings.SSO_*_CLIENT_SECRET` |

---

## OWASP Top 10 Assessment

### A01:2021 -- Broken Access Control

**Controls implemented:**
- JWT authentication required for all API endpoints (except health check)
- RBAC with three roles: `admin > analyst > readonly`
- API key authentication as alternative to JWT
- Route-level permission checks via FastAPI dependencies

**Audit steps:**
```
[ ] Verify unauthenticated requests return 401
[ ] Verify readonly users cannot create/update/delete
[ ] Verify analyst users cannot manage users or system config
[ ] Verify JWT tokens expire correctly (30 min access, 7 day refresh)
[ ] Verify API keys are scoped to user permissions
```

### A02:2021 -- Cryptographic Failures

**Controls implemented:**
- Feed credentials encrypted with Fernet symmetric encryption
- Passwords hashed with bcrypt
- JWT signed with HS256 using SECRET_KEY
- HTTPS enforced in production (via reverse proxy)

**Audit steps:**
```
[ ] Verify FEED_ENCRYPTION_KEY is a valid Fernet key
[ ] Verify password hashing uses bcrypt (not MD5/SHA1)
[ ] Verify SECRET_KEY is cryptographically random (32+ bytes)
[ ] Verify no secrets in API responses
```

### A03:2021 -- Injection

**Controls implemented:**
- SQLAlchemy ORM prevents SQL injection (parameterized queries)
- Pydantic v2 validates all input with strict schemas
- Elasticsearch queries use query DSL (not raw strings)

**Audit steps:**
```
[ ] Verify no raw SQL strings in codebase (search for text(), execute())
[ ] Verify all API inputs pass through Pydantic models
[ ] Verify Elasticsearch queries use proper escaping
```

### A04:2021 -- Insecure Design

**Controls implemented:**
- Layered architecture: routes -> services -> models
- Input validation at schema level before business logic
- Rate limiting on enrichment API calls
- Observable deduplication prevents data quality issues

### A05:2021 -- Security Misconfiguration

**Audit steps:**
```
[ ] Verify OpenAPI docs disabled in production (ENVIRONMENT=production)
[ ] Verify CORS origins are restrictive (not wildcard)
[ ] Verify default admin password changed
[ ] Verify Elasticsearch xpack.security settings
[ ] Verify Redis has no public exposure (bound to internal network)
[ ] Verify PostgreSQL not exposed externally (127.0.0.1 binding)
```

### A06:2021 -- Vulnerable Components

**Audit steps:**
```
[ ] Run pip-audit with zero vulnerabilities
[ ] Run npm audit with zero high/critical
[ ] Run Trivy with zero critical findings
[ ] Verify all base images are recent (postgres:16, redis:7, es:8.15)
```

### A07:2021 -- Authentication Failures

**Controls implemented:**
- No default weak passwords (admin password configurable via env)
- JWT token expiration enforced
- SSO integration (Azure AD, Google, OIDC)
- Account lockout not yet implemented (document as TODO)

### A08:2021 -- Data Integrity Failures

**Controls implemented:**
- Alembic migration versioning prevents schema drift
- Feed data normalized through connector pipeline
- Observable deduplication via unique constraint

### A09:2021 -- Logging and Monitoring

**Controls implemented:**
- Structured logging via Python `logging` module
- Audit log table (`audit_logs`) tracks user actions
- Feed run history tracked in `feed_runs` table
- Enrichment run history in `enrichment_runs` table

### A10:2021 -- Server-Side Request Forgery (SSRF)

**Audit steps:**
```
[ ] Verify feed URLs are validated (no internal network access)
[ ] Verify enrichment providers use hardcoded base URLs
[ ] Verify scraper connector has URL allowlisting
```

---

## Security Hardening Checklist

### Pre-Production

```
[ ] Change default admin password
[ ] Generate strong SECRET_KEY (32+ bytes)
[ ] Generate proper FEED_ENCRYPTION_KEY (Fernet)
[ ] Set ENVIRONMENT=production (disables docs, debug)
[ ] Configure CORS_ORIGINS to specific frontend URL
[ ] Set up HTTPS via reverse proxy (nginx/Traefik)
[ ] Restrict PostgreSQL to internal network only
[ ] Restrict Redis to internal network only
[ ] Restrict Elasticsearch to internal network only
[ ] Review Docker resource limits
```

### Ongoing

```
[ ] Weekly dependency audit (pip-audit, npm audit)
[ ] Monthly container image rebuild with latest patches
[ ] Quarterly OWASP review
[ ] Rotate FEED_ENCRYPTION_KEY annually (re-encrypt credentials)
[ ] Monitor audit logs for suspicious activity
[ ] Review RBAC assignments
```

---

## Tools

| Tool | Purpose |
|------|---------|
| `tools/security/scan.sh` | Run full security scan suite (Bandit + pip-audit + npm audit) |

---

## Related Files

- **Auth:** `src/cti/core/security.py`, `src/cti/services/auth_service.py`
- **Config:** `src/cti/core/config.py` (Settings with SecretStr)
- **SSO:** `src/cti/sso/` (Azure AD, Google, OIDC providers)
- **Audit:** `src/cti/models/audit_log.py`, `src/cti/services/audit_service.py`
- **Feed Encryption:** `src/cti/services/feed_service.py` (get_feed_auth_config)
- **CI:** `.github/workflows/security.yml`
