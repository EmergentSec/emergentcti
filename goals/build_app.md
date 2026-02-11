# Build App -- ATLAS Workflow for EmergentCTI

## Goal

Build production-ready features for the EmergentCTI platform using the ATLAS 5-step process. Every new feature, endpoint, or UI component follows this workflow to prevent rework and ensure reliability.

**ATLAS** is a 5-step process:

| Step | Phase | What You Do |
|------|-------|-------------|
| **A** | Architect | Define the feature, its users, and success criteria |
| **T** | Trace | Data schema, service layer, integration map |
| **L** | Link | Validate all connections before building |
| **A** | Assemble | Build with the CTI layered architecture |
| **S** | Stress-test | Test functionality, error handling, edge cases |

For production releases, add:
+ V - Validate (security/input sanitization, Bandit SAST, edge cases, unit tests)
+ M - Monitor (logging, health checks, Celery task monitoring)

---

## A -- Architect

**Purpose:** Know exactly what you are building before touching code.

### Questions to Answer

1. **What problem does this solve?**
   - One sentence. Example: "Analysts need to see which observables share infrastructure."

2. **Who is this for?**
   - Specific role: SOC analyst, threat intel lead, platform admin
   - Not "everyone"

3. **What does success look like?**
   - Measurable: "Graph view renders 500 nodes in under 2 seconds"
   - Not vague: "It works"

4. **What are the constraints?**
   - API rate limits (enrichment providers)
   - Database performance (PostgreSQL + Elasticsearch sync)
   - Docker resource limits (512MB per service)

### Output

```markdown
## Feature Brief
- **Problem:** [One sentence]
- **User:** [SOC analyst / admin / API consumer]
- **Success:** [Measurable outcome]
- **Constraints:** [Rate limits, memory, external dependencies]
```

---

## T -- Trace

**Purpose:** Design before building. Define schema, services, and integrations.

### Data Schema

Define or extend models BEFORE writing routes:

```
Models to create/modify:
- src/cti/models/   (SQLAlchemy ORM)
- src/cti/schemas/  (Pydantic v2 request/response)

Relationships:
- Observable -> Feed (M:N via observable_sources)
- Observable -> Tag (M:N via observable_tags)
- Observable -> EnrichmentRun (1:N)
- Feed -> FeedRun (1:N)
```

### Integrations Map

| Service | Purpose | Location | Notes |
|---------|---------|----------|-------|
| PostgreSQL | Primary data store | models/ | Alembic migrations required |
| Elasticsearch | Full-text search | services/search_service.py | Index sync on write |
| Redis | Cache + Celery broker | core/redis.py | TTL-based caching |
| Celery | Async task processing | worker.py | Feed ingestion, enrichment |
| External APIs | Enrichment providers | enrichment/ | Rate-limited, async |

### Technology Decisions

- Backend routes go in `src/cti/api/v1/`
- Business logic goes in `src/cti/services/`
- Database models use SQLAlchemy 2.0 mapped_column style
- All schemas use Pydantic v2 with strict validation
- Frontend components go in `frontend/src/`

### Edge Cases

Document what could break:

- Elasticsearch index drift (schema mismatch after migration)
- Celery task timeout on large feed ingestion
- Duplicate observable handling (ON CONFLICT upsert)
- Feed auth token expiry mid-ingestion
- Redis connection pool exhaustion under load

### Output

- Data schema additions (models + Pydantic schemas)
- Migration plan (`alembic revision --autogenerate -m "description"`)
- Integration checklist
- Edge cases documented

---

## L -- Link

**Purpose:** Validate all connections BEFORE building. Do not build for 2 hours then discover the database migration fails.

### Connection Validation Checklist

```
[ ] PostgreSQL connection tested (docker compose exec api python -c "from cti.core.database import ...")
[ ] Alembic migration dry-run successful
[ ] Elasticsearch index accessible and mapping correct
[ ] Redis connection and Celery broker responding
[ ] Environment variables set in .env
[ ] External API keys valid (if enrichment feature)
[ ] Frontend dev server starts (cd frontend && npm run dev)
```

### How to Test

**Database:**
```bash
docker compose exec api python -c "
from cti.core.database import sync_engine
from sqlalchemy import text
with sync_engine.connect() as c:
    print(c.execute(text('SELECT 1')).scalar())
"
```

**Elasticsearch:**
```bash
curl -s http://localhost:9200/_cluster/health | python -m json.tool
```

**Redis + Celery:**
```bash
docker compose exec worker celery -A cti.worker inspect ping
```

### Output

All connections verified. If anything fails, fix it before proceeding to Assemble.

---

## A -- Assemble

**Purpose:** Build the feature following CTI's layered architecture.

### Build Order

1. **Database layer first** -- Models + migration
   - Create/modify model in `src/cti/models/`
   - Generate migration: `uv run alembic revision --autogenerate -m "add feature_x"`
   - Apply migration: `uv run alembic upgrade head`

2. **Service layer second** -- Business logic
   - Create service in `src/cti/services/`
   - Handle validation, deduplication, and error cases
   - Write to both PostgreSQL and Elasticsearch where needed

3. **API layer third** -- Routes and schemas
   - Create Pydantic schemas in `src/cti/schemas/`
   - Create routes in `src/cti/api/v1/`
   - Register router in `src/cti/api/v1/router.py`

4. **Frontend last** -- React components
   - API client functions in `frontend/src/api/`
   - Components in `frontend/src/components/`
   - Pages in `frontend/src/pages/`

### Architecture Rules

- Models never import from services or API layers
- Services never import from API layers
- Routes delegate all logic to services
- All database operations use async sessions
- Observable deduplication by type + value composite key

### Output

Working feature with:
- Migration applied
- API endpoints responding at `/api/v1/...`
- Frontend rendering (if applicable)
- Elasticsearch index updated (if search-related)

---

## S -- Stress-test

**Purpose:** Test before shipping. Do not merge untested features.

### Functional Testing

```bash
# Run all tests
uv run pytest

# Run specific test file
uv run pytest tests/test_feature.py -v

# Run with coverage
uv run pytest --cov=src/cti
```

### Integration Testing

```
[ ] API endpoints return correct status codes
[ ] Database writes persist and read back correctly
[ ] Elasticsearch indexes sync after observable creation
[ ] Celery tasks execute without errors
[ ] Auth middleware blocks unauthenticated requests
```

### Edge Case Testing

```
[ ] Invalid input returns 422 with clear error messages
[ ] Duplicate observables upsert correctly (ON CONFLICT)
[ ] Empty responses return proper pagination metadata
[ ] Large payloads do not crash (bulk import of 10k observables)
[ ] Concurrent writes do not cause race conditions
```

### Linting and Type Checks

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy src/
cd frontend && npx tsc --noEmit
```

### Tools

- `tools/test/run_tests.sh` -- Run full backend test suite
- `tools/test/lint_check.sh` -- Run linting and formatting checks

### Output

Test report with:
- What passed
- What failed
- What needs fixing before merge

---

## Anti-Patterns (What NOT to Do)

1. **Building before designing** -- Schema changes cascade into service rewrites
2. **Skipping migration testing** -- Broken migrations corrupt production data
3. **No input validation** -- Pydantic validators exist for a reason; use them
4. **Hardcoding config** -- Use `core/config.py` Settings class and environment variables
5. **Ignoring Elasticsearch sync** -- Stale search index leads to user confusion
6. **Writing business logic in routes** -- Routes delegate to services, always

---

## GOTCHA Layer Mapping

| ATLAS Step | GOTCHA Layer |
|------------|--------------|
| Architect | Goals (define the process) |
| Trace | Context (reference patterns, schemas) |
| Link | Args (environment setup, config validation) |
| Assemble | Tools (execution scripts) |
| Stress-test | Orchestration (AI validates results) |

---

## Related Files

- **Args:** `args/defaults.yaml` (platform behavior settings)
- **Context:** `context/observable_types.md`, `context/architecture.md`
- **Hard Prompts:** `hardprompts/report_generation.md`
- **Tools:** `tools/test/run_tests.sh`, `tools/deploy/docker_deploy.sh`
