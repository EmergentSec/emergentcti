# CLAUDE.md

## GOTCHA Framework — How This System Operates

This system uses the **GOTCHA Framework** — a 6-layer architecture for agentic systems:

**GOT** (The Engine):
- **Goals** (`goals/`) — What needs to happen (process definitions)
- **Orchestration** — The AI manager (you) that coordinates execution
- **Tools** (`tools/`) — Deterministic scripts that do the actual work

**CHA** (The Context):
- **Context** (`context/`) — Reference material and domain knowledge
- **Hard prompts** (`hardprompts/`) — Reusable instruction templates
- **Args** (`args/`) — Behavior settings that shape how the system acts

You're the manager of a multi-layer agentic system. LLMs are probabilistic (educated guesses). Business logic is deterministic (must work the same way every time).
This structure exists to bridge that gap through **separation of concerns**.

---

### Why This Structure Exists

When AI tries to do everything itself, errors compound fast.
90% accuracy per step sounds good until you realize that's ~59% accuracy over 5 steps.

The solution:

* Push **reliability** into deterministic code (tools)
* Push **flexibility and reasoning** into the LLM (manager)
* Push **process clarity** into goals
* Push **behavior settings** into args files
* Push **domain knowledge** into the context layer
* Keep each layer focused on a single responsibility

You make smart decisions. Tools execute perfectly.

---

### The Layered Structure

#### 1. Process Layer — Goals (`goals/`)

* Task-specific instructions in clear markdown
* Each goal defines: objective, inputs, which tools to use, expected outputs, edge cases
* Written like you're briefing someone competent
* Only modified with explicit permission
* Goals tell the system **what** to achieve, not how it should behave today

#### 2. Orchestration Layer — Manager (AI Role)

* Reads the relevant goal
* Decides which tools (scripts) to use and in what order
* Applies args settings to shape behavior
* References context for domain knowledge (observable types, feed sources, confidence models, etc.)
* Handles errors, asks clarifying questions, makes judgment calls
* Never executes work — it delegates intelligently
* Example: Don't parse threat feeds yourself. Read `goals/ingest_feed.md`, understand requirements, then call `tools/deploy/docker_deploy.sh` or `tools/db/run_migrations.sh` with the correct parameters.

#### 3. Execution Layer — Tools (`tools/`)

* Shell and Python scripts organized by workflow
* Each has **one job**: API calls, data processing, deployments, database work, etc.
* Fast, documented, testable, deterministic
* They don't think. They don't decide. They just execute.
* Credentials + environment variables handled via `.env`
* All tools must be listed in `tools/manifest.md` with a one-sentence description

#### 4. Args Layer — Behavior (`args/`)

* YAML/JSON files controlling how the system behaves right now
* Examples: confidence thresholds, feed polling intervals, enrichment settings, deployment targets
* Changing args changes behavior without editing goals or tools
* The manager reads args before running any workflow

#### 5. Context Layer — Domain Knowledge (`context/`)

* Static reference material the system uses to reason
* Examples: observable type definitions, feed source documentation, STIX/TAXII specs, confidence scoring models, architecture diagrams
* Shapes quality and style — not process or behavior

#### 6. Hard Prompts Layer — Instruction Templates (`hardprompts/`)

* Reusable text templates for LLM sub-tasks
* Example: threat report generation, feed analysis summaries, incident response templates, observable enrichment prompts
* Hard prompts are fixed instructions, not context or goals

---

### How to Operate

#### 1. Check for existing goals first

Before starting a task, check `goals/manifest.md` for a relevant workflow.
If a goal exists, follow it — goals define the full process for common tasks.

#### 2. Check for existing tools

Before writing new code, read `tools/manifest.md`.
This is the index of all available tools.

If a tool exists, use it.
If you create a new tool script, you **must** add it to the manifest with a 1-sentence description.

#### 3. When tools fail, fix and document

* Read the error and stack trace carefully
* Update the tool to handle the issue (ask if API credits are required)
* Add what you learned to the goal (rate limits, batching rules, timing quirks)
* Example: tool hits 429 -> find batch endpoint -> refactor -> test -> update goal
* If a goal exceeds a reasonable length, propose splitting it into a primary goal + technical reference

#### 4. Treat goals as living documentation

* Update only when better approaches or API constraints emerge
* Never modify/create goals without explicit permission
* Goals are the instruction manual for the entire system

#### 5. Communicate clearly when stuck

If you can't complete a task with existing tools and goals:

* Explain what's missing
* Explain what you need
* Do not guess or invent capabilities

#### 6. Guardrails — Learned Behaviors

Document Claude-specific mistakes here (not script bugs—those go in goals):

* Always check `tools/manifest.md` before writing a new script
* Verify tool output format before chaining into another tool
* Don't assume APIs support batch operations—check first
* When a workflow fails mid-execution, preserve intermediate outputs before retrying
* Read the full goal before starting a task—don't skim
* **NEVER delete feed data or observables in bulk without explicit confirmation** — Bulk deletion of threat intel data is destructive and irreversible. Always confirm with the user before proceeding.
* **Always rebuild Docker containers after code changes** — Running containers will not reflect source changes until rebuilt with `docker compose up -d --build`.
* **Run alembic upgrade head after creating new migrations** — New migration files must be applied to the database to take effect.

*(Add new guardrails as mistakes happen. Keep this under 15 items.)*

---

### First Run Initialization

**On first session in a new environment, check if memory infrastructure exists. If not, create it:**

1. Check if `memory/MEMORY.md` exists
2. If missing, this is a fresh environment — initialize:

```bash
# Create directory structure
mkdir -p memory/logs
mkdir -p data

# Create MEMORY.md with default template
cat > memory/MEMORY.md << 'EOF'
# Persistent Memory

> This file contains curated long-term facts, preferences, and context that persist across sessions.
> The AI reads this at the start of each session. You can edit this file directly.

## User Preferences

- (Add your preferences here)

## Key Facts

- (Add key facts about your work/projects)

## Learned Behaviors

- Always check tools/manifest.md before creating new scripts
- Follow GOTCHA framework: Goals, Orchestration, Tools, Context, Hardprompts, Args

## Current Projects

- (List active projects)

## Technical Context

- Framework: GOTCHA (6-layer agentic architecture)

---

*Last updated: (date)*
*This file is the source of truth for persistent facts. Edit directly to update.*
EOF

# Create today's log file
echo "# Daily Log: $(date +%Y-%m-%d)" > "memory/logs/$(date +%Y-%m-%d).md"
echo "" >> "memory/logs/$(date +%Y-%m-%d).md"
echo "> Session log for $(date +'%A, %B %d, %Y')" >> "memory/logs/$(date +%Y-%m-%d).md"
echo "" >> "memory/logs/$(date +%Y-%m-%d).md"
echo "---" >> "memory/logs/$(date +%Y-%m-%d).md"
echo "" >> "memory/logs/$(date +%Y-%m-%d).md"
echo "## Events & Notes" >> "memory/logs/$(date +%Y-%m-%d).md"
echo "" >> "memory/logs/$(date +%Y-%m-%d).md"

# Initialize core databases (they auto-create tables on first connection)
python3 -c "
import sqlite3
from pathlib import Path

data_dir = Path('data')
data_dir.mkdir(exist_ok=True)

# Memory database
conn = sqlite3.connect('data/memory.db')
conn.execute('''CREATE TABLE IF NOT EXISTS memory_entries (
    id INTEGER PRIMARY KEY,
    content TEXT NOT NULL,
    entry_type TEXT DEFAULT 'fact',
    importance INTEGER DEFAULT 5,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
)''')
conn.commit()
conn.close()

# Activity/task tracking database
conn = sqlite3.connect('data/activity.db')
conn.execute('''CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    source TEXT,
    request TEXT,
    status TEXT DEFAULT 'pending',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    completed_at DATETIME,
    summary TEXT
)''')
conn.commit()
conn.close()

print('Memory infrastructure initialized!')
"
```

3. Confirm to user: "Memory system initialized. I'll remember things across sessions now."

---

### Memory Protocol

The system has persistent memory across sessions. At session start, read the memory context:

**Load Memory:**
1. Read `memory/MEMORY.md` for curated facts and preferences
2. Read today's log: `memory/logs/YYYY-MM-DD.md`
3. Read yesterday's log for continuity

```bash
python tools/memory/memory_read.py --format markdown
```

**During Session:**
- Append notable events to today's log: `python tools/memory/memory_write.py --content "event" --type event`
- Add facts to the database: `python tools/memory/memory_write.py --content "fact" --type fact --importance 7`
- For truly persistent facts (always loaded), update MEMORY.md: `python tools/memory/memory_write.py --update-memory --content "New preference" --section user_preferences`

**Search Memory:**
- Keyword search: `python tools/memory/memory_db.py --action search --query "keyword"`
- Semantic search: `python tools/memory/semantic_search.py --query "related concept"`
- Hybrid search (best): `python tools/memory/hybrid_search.py --query "what does user prefer"`

**Memory Types:**
- `fact` - Objective information
- `preference` - User preferences
- `event` - Something that happened
- `insight` - Learned pattern or realization
- `task` - Something to do
- `relationship` - Connection between entities

---

### The Continuous Improvement Loop

Every failure strengthens the system:

1. Identify what broke and why
2. Fix the tool script
3. Test until it works reliably
4. Update the goal with new knowledge
5. Next time -> automatic success

---

### File Structure (GOTCHA Directories)

**Where Things Live:**

* `goals/` — Process Layer (what to achieve)
* `tools/` — Execution Layer (organized by workflow)
* `args/` — Args Layer (behavior settings)
* `context/` — Context Layer (domain knowledge)
* `hardprompts/` — Hard Prompts Layer (instruction templates)
* `memory/` — Persistent memory (MEMORY.md, daily logs)
* `data/` — Runtime data (memory.db, activity.db)
* `.tmp/` — Temporary work (scrapes, raw data, intermediate files). Disposable.
* `.env` — API keys + environment variables
* `goals/manifest.md` — Index of available goal workflows
* `tools/manifest.md` — Master list of tools and their functions

**Deliverables vs Scratch:**

* **Deliverables**: outputs needed by the user (reports, processed data, deployments, etc.)
* **Scratch Work**: temp files (raw scrapes, CSVs, research). Always disposable.
* Never store important data in `.tmp/`.

---

### Your Job in One Sentence

You sit between what needs to happen (goals) and getting it done (tools).
Read instructions, apply args, use context, delegate well, handle failures, and strengthen the system with each run.

Be direct.
Be reliable.
Get shit done.

---

## Project Overview

CTI (Cyber Threat Intelligence) Platform - A threat intelligence aggregation and analysis platform inspired by OpenCTI, SOCRadar, MISP, and AlienVault OTX. Designed for homelab deployment initially, with plans for open source release via Docker Compose and potential commercialization.

## Technology Stack

- **Backend**: Python 3.12+ with FastAPI
- **Frontend**: React 18 + TypeScript (Vite), Tailwind CSS, shadcn/ui-style components, TanStack Query
- **Database**: PostgreSQL 16 (primary data store)
- **Cache/Queue**: Redis 7 (caching + Celery broker)
- **Search**: Elasticsearch 8.15 (observable search and correlation)
- **Task Processing**: Celery with Redis broker (feed ingestion workers + Beat scheduler)
- **Auth**: JWT (access + refresh tokens) + API keys, RBAC (admin > analyst > readonly)
- **Containerization**: Docker Compose (6 services on port 8080)

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                   Frontend (React/Nginx :8080)               │
├─────────────────────────────────────────────────────────────┤
│                      API Gateway (FastAPI :8000)             │
├─────────────────────────────────────────────────────────────┤
│  /api/v1/observables  │  /api/v1/feeds  │  /api/v1/search  │
│  /api/v1/auth         │  /api/v1/dashboard                  │
└───────────┬───────────┴────────┬────────┴────────┬─────────┘
            │                    │                 │
┌───────────▼───────────┐  ┌─────▼─────┐  ┌───────▼────────┐
│   Observable Service  │  │   Feed    │  │  Search/Query  │
│   (CRUD + Enrichment) │  │  Ingestion│  │    Engine      │
└───────────┬───────────┘  └─────┬─────┘  └───────┬────────┘
            │                    │                 │
┌───────────▼────────────────────▼─────────────────▼────────┐
│                     Data Layer                             │
│  PostgreSQL (observables, feeds, users, relationships)     │
│  Elasticsearch (full-text search, correlation)             │
│  Redis (cache, celery broker)                              │
└────────────────────────────────────────────────────────────┘
```

## Observable Types

Core observable types (defined in `ObservableType` enum):
- `ip-addr` (IPv4/IPv6)
- `domain-name`
- `url`
- `file-hash` (MD5=32, SHA1=40, SHA256=64, SHA512=128 hex chars)
- `email-addr`
- `command-line`
- `user-agent`
- `certificate` (SHA1/SHA256 fingerprint)
- `asn` (format: `AS\d+`)
- `cidr` (CIDR notation validated via `ipaddress.ip_network`)

Each type has custom Pydantic validators in `src/cti/schemas/observable.py`.

## Feed Connectors

Feeds are pluggable connectors that normalize external threat intel into the internal schema. All inherit from `BaseFeedConnector` (`src/cti/feeds/base.py`):
- **API feeds** (`api_connector.py`): REST polling with configurable auth, pagination (page/offset/cursor), field mapping
- **TAXII feeds** (`taxii_connector.py`): TAXII 2.1 via taxii2-client, STIX 2.x parsing via stix2
- **File feeds** (`file_connector.py`): CSV (column mapping), JSON (dot-path), STIX bundles
- **Web scraping** (`scraper_connector.py`): BeautifulSoup + lxml, IOC regex extraction, defanging support

Factory: `src/cti/feeds/__init__.py` — `get_connector(feed)` returns the right connector class.

## Development Commands

```bash
# Setup
uv sync                              # Install dependencies
cp .env.example .env                 # Configure environment (set SECRET_KEY, POSTGRES_PASSWORD, FEED_ENCRYPTION_KEY)
docker-compose up -d postgres redis elasticsearch  # Start infrastructure services

# Backend development
uv run fastapi dev src/cti/main.py   # Run dev server with hot reload (port 8000)
uv run pytest                        # Run all tests
uv run pytest tests/test_file.py::test_name -v  # Run single test
uv run ruff check .                  # Lint
uv run ruff format .                 # Format
uv run mypy src/                     # Type check

# Frontend development
cd frontend && npm install           # Install frontend deps
cd frontend && npm run dev           # Dev server (port 5173, proxies /api to 8000)
cd frontend && npm run build         # Production build
cd frontend && npx tsc --noEmit      # Type check
cd frontend && npx eslint src/       # Lint

# Database
uv run alembic upgrade head          # Run migrations
uv run alembic revision --autogenerate -m "description"  # Create migration

# Celery workers
uv run celery -A cti.worker worker -l info -B  # Start worker with Beat scheduler

# Full Docker deployment
docker-compose up --build -d         # Build and start all 6 services
# Frontend at http://localhost:8080 (default login: admin/admin)
```

## Project Structure

```
src/cti/
├── main.py              # FastAPI app factory with lifespan (ES index, admin user)
├── worker.py            # Celery tasks: run_feed_task, check_scheduled_feeds, reindex_elasticsearch
├── api/
│   └── v1/
│       ├── router.py    # Aggregates all sub-routers under /api/v1
│       ├── auth.py      # Login, register, refresh, me, API key
│       ├── observables.py # CRUD + stats + filtering/pagination
│       ├── feeds.py     # CRUD + trigger + run history
│       ├── search.py    # Elasticsearch full-text search
│       └── dashboard.py # Aggregated stats
├── core/
│   ├── config.py        # pydantic-settings, SecretStr for sensitive values
│   ├── database.py      # Async engine (FastAPI) + sync engine (Celery)
│   ├── security.py      # JWT, bcrypt, API key generation, Fernet encryption
│   ├── elasticsearch.py # ES client factory + index mapping
│   ├── redis.py         # Redis client factory
│   └── dependencies.py  # get_current_user (JWT/API key), require_role, CurrentUser/AnalystUser/AdminUser
├── models/
│   ├── base.py          # DeclarativeBase, UUIDMixin, TimestampMixin
│   ├── observable.py    # Observable + association tables (tags, sources)
│   ├── feed.py          # Feed + FeedRun
│   ├── user.py          # User with role enum
│   ├── tag.py           # Tag
│   └── relationship.py  # ObservableRelationship
├── schemas/
│   ├── observable.py    # Create/Update/Response + per-type validators
│   ├── feed.py          # Create/Update/Response + cron validation
│   ├── auth.py          # Login/Register/Token/User/ApiKey
│   ├── search.py        # SearchRequest/Hit/Response
│   └── dashboard.py     # DashboardStats
├── services/
│   ├── observable_service.py  # CRUD with ON CONFLICT upsert dedup
│   ├── feed_service.py        # CRUD with encrypted auth config
│   ├── search_service.py      # ES search, index, bulk_index
│   ├── auth_service.py        # Auth, register, refresh, API key, initial admin
│   └── dashboard_service.py   # Aggregated stats queries
└── feeds/
    ├── base.py          # BaseFeedConnector ABC, FeedResult dataclass
    ├── api_connector.py # REST API polling
    ├── taxii_connector.py # TAXII 2.1 + STIX parsing
    ├── file_connector.py  # CSV/JSON/STIX file ingestion
    └── scraper_connector.py # Web scraping with IOC regex

frontend/src/
├── main.tsx             # React entry point
├── App.tsx              # Router + QueryClient + AuthProvider
├── index.css            # Tailwind + CSS custom properties (dark/light themes)
├── api/                 # Axios client with JWT refresh queue, API modules
├── contexts/            # AuthContext (JWT state management)
├── hooks/               # useAuth, useObservables, useFeeds, useSearch, useTheme
├── components/
│   ├── ui/              # Button, Input, Badge, Card, Dialog, Select, Table, DropdownMenu
│   ├── layout/          # AppLayout, Sidebar, Header
│   ├── observables/     # ObservableTable, ObservableBadge
│   ├── feeds/           # FeedCard, FeedForm, FeedRunHistory
│   ├── dashboard/       # StatsGrid, TypeDistribution (Recharts), FeedHealthPanel
│   └── common/          # ConfidenceMeter, Pagination, LoadingSpinner, ErrorBoundary
├── pages/               # Login, Dashboard, Observables, ObservableDetail, Feeds, Search, Settings
└── types/               # TypeScript interfaces for observable, feed, auth, search, api

tests/
├── conftest.py          # SQLite test DB, user fixtures (admin/analyst/readonly), auth headers
├── test_api/            # Auth, observables (CRUD/dedup/validation/RBAC), feeds, search
├── test_services/       # Observable upsert dedup, feed encryption
└── test_feeds/          # Observable type validation tests

# GOTCHA Framework directories
goals/                   # Process definitions (what to achieve)
tools/                   # Deterministic scripts (deploy, db, test, security, memory)
args/                    # Behavior settings (defaults.yaml)
context/                 # Domain knowledge (observable types, feed sources, architecture)
hardprompts/             # Instruction templates (reports, analysis, incident response)
memory/                  # Persistent memory (MEMORY.md, daily logs)
data/                    # Runtime data (memory.db, activity.db)
```

## Docker Services

| Service | Image | Port | Notes |
|---------|-------|------|-------|
| postgres | postgres:16-alpine | 5432 (localhost) | Primary data store |
| redis | redis:7-alpine | internal | Celery broker + cache |
| elasticsearch | ES 8.15.0 | internal | Full-text search |
| api | Custom (Dockerfile) | internal (8000) | FastAPI + Gunicorn |
| worker | Same as api | internal | Celery + Beat scheduler |
| frontend | Custom (frontend/Dockerfile) | **8080 -> host** | Nginx + React SPA |

## Post-Change Workflow

After making code changes, always rebuild the affected Docker containers:

```bash
# Rebuild and restart all application containers (frontend, api, worker)
docker compose up -d --build frontend api worker

# If only backend changed:
docker compose up -d --build api worker

# If only frontend changed:
docker compose up -d --build frontend
```

This ensures the running containers reflect the latest code. The frontend build runs `tsc && vite build` inside the container, so TypeScript errors will surface during the Docker build step.

## Conventions

- Use `uv` for dependency management (pyproject.toml)
- Alembic for database migrations (migrations in `alembic/versions/`)
- Pydantic v2 for all schemas with strict validation and custom per-type validators
- Type hints required on all function signatures
- Observable deduplication by `(type, value)` composite unique constraint — upsert on conflict raises confidence, updates last_seen
- All feed connectors inherit from `BaseFeedConnector` abstract class
- API versioning via URL prefix (`/api/v1/`)
- RBAC: readonly < analyst < admin, enforced via `CurrentUser`/`AnalystUser`/`AdminUser` dependencies
- Feed credentials encrypted at rest with Fernet symmetric encryption
- JWT access tokens expire in 30min, refresh tokens in 7 days
- Frontend uses dark mode by default, TanStack Query with 30s stale time
- Tests use SQLite in-memory database with async session override
- CI: ruff + mypy + pytest + ESLint + tsc + vitest
- Security scanning: Bandit SAST, pip-audit, npm audit, Trivy image scan, TruffleHog secrets

## GOTCHA Layer Mapping for CTI

| Layer | Directory | CTI Implementation |
|-------|-----------|-------------------|
| Goals | `goals/` | Feed ingestion, enrichment, deployment, testing, security audit workflows |
| Orchestration | (AI manager) | Claude Code coordinates execution using goals and tools |
| Tools | `tools/` | Deploy scripts, migration helpers, test runners, security scanners, memory system |
| Context | `context/` | Observable types, feed sources, confidence model, architecture docs |
| Hardprompts | `hardprompts/` | Report generation, feed analysis, incident response templates |
| Args | `args/` | defaults.yaml — confidence thresholds, feed settings, enrichment config |
