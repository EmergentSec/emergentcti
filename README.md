<p align="center">
  <img src="assets/horizontal-logo.svg" alt="EmergentCTI" width="400">
</p>

<p align="center">
  Open-source cyber threat intelligence platform for aggregating, enriching, and correlating indicators of compromise from multiple feeds.
</p>

<p align="center">
  <a href="#quick-start">Quick Start</a> &middot;
  <a href="#features">Features</a> &middot;
  <a href="#architecture">Architecture</a> &middot;
  <a href="#configuration">Configuration</a> &middot;
  <a href="#development">Development</a>
</p>

---

## Quick Start

**Prerequisites:** Docker and Docker Compose

```bash
# Clone the repository
git clone https://github.com/EmergentSec/emergentcti.git
cd emergentcti

# Configure environment
cp .env.example .env

# Generate required secrets
sed -i '' "s/POSTGRES_PASSWORD=change-me/POSTGRES_PASSWORD=$(openssl rand -hex 16)/" .env
sed -i '' "s/SECRET_KEY=change-me-to-a-random-secret-key/SECRET_KEY=$(openssl rand -hex 32)/" .env

# Generate Fernet encryption key for feed credentials
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# Paste the output into FEED_ENCRYPTION_KEY= in .env

# Start the platform
docker compose up -d --build
```

Open **http://localhost:8080** and log in with `admin` / `admin`.

That's it. All 6 services (PostgreSQL, Redis, Elasticsearch, API, Worker, Frontend) start automatically with health checks and dependency ordering. Database migrations run on first boot.

---

## Features

### Feed Ingestion
- **4 connector types:** REST API, TAXII 2.1/STIX, File (CSV/JSON/STIX bundles), Web Scraper
- **6 pre-configured feeds** out of the box: AbuseIPDB, Emerging Threats, Blocklist.de, Tor Exit Nodes, OpenPhish, URLhaus
- Cron-based scheduling with configurable intervals
- Feed credentials encrypted at rest with Fernet symmetric encryption
- Add custom feeds through the UI with a preset wizard or manual configuration

### Observable Management
- **10 observable types:** IP address, domain, URL, file hash (MD5/SHA1/SHA256/SHA512), email, command-line, user-agent, certificate fingerprint, ASN, CIDR
- Automatic deduplication via composite unique constraint on (type, value)
- Per-observable confidence scoring with multi-source MAX aggregation
- Tagging, categorization, TLP marking, and notes
- Bulk operations: update, delete, enrich, export
- Full-text search powered by Elasticsearch

### Enrichment
- **5 providers:** VirusTotal, AbuseIPDB, Shodan, GreyNoise, URLScan
- Auto-enrichment pipeline triggered on feed ingestion
- Provider-specific confidence extraction with weighted scoring
- Rate limiting per provider
- Enrichment history with full result data

### Confidence Scoring
- Per-feed default confidence (e.g., AbuseIPDB=90, Tor Exit Nodes=30)
- Multi-source aggregation: `func.greatest()` keeps the highest score across feeds
- Enrichment-based updates: weighted average (60% provider, 40% existing)
- Lifecycle decay: -5 points/week after 30 days stale, floor at 10
- Indicator expiration via configurable TTL per feed

### Correlation Engine
- Rule-based correlation across observables
- Automatic detection of related indicators
- Observable relationship mapping (communicates-with, resolves-to, drops, etc.)

### Threat Intelligence
- **MITRE ATT&CK** technique mapping for observables
- **Threat Actor** profiles linked to observables and campaigns
- **Campaign** tracking with timelines and linked entities
- **Interactive Graph Explorer** for visualizing entity relationships

### Reporting
- Three report types: Threat Summary, Observable Deep-Dive, Campaign Brief
- HTML generation with Jinja2 templates
- Background generation via Celery tasks
- Download and management through the UI

### Alerting & Webhooks
- Configurable alert rules
- Webhook notifications to external systems
- Saved searches with re-run capability

### Platform
- **Authentication:** JWT (access + refresh tokens) + API keys
- **RBAC:** Three roles — Admin, Analyst, Read-only
- **SSO:** Google, Azure AD/Entra, generic OIDC
- **Audit logging** for all state-changing operations
- **STIX/CSV/JSON export and import**
- Dark mode UI by default

---

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│                  Frontend (React/Nginx :8080)             │
├──────────────────────────────────────────────────────────┤
│                    API Gateway (FastAPI :8000)            │
├──────────────────────────────────────────────────────────┤
│  Observables │ Feeds │ Search │ Enrichment │ Correlations │
│  Auth │ Alerts │ Reports │ Graph │ Threat Actors │ SSO   │
└──────┬───────┴───┬───┴───┬───┴──────┬───────────────────┘
       │           │       │          │
┌──────▼──┐  ┌─────▼──┐  ┌▼────────┐ │
│ Postgres │  │ Redis  │  │  Elastic │ │
│   :5432  │  │ :6379  │  │  :9200   │ │
└─────────┘  └────────┘  └─────────┘ │
                                      │
                              ┌───────▼────────┐
                              │  Celery Worker  │
                              │  + Beat Sched.  │
                              └────────────────┘
```

| Service | Image | Purpose |
|---------|-------|---------|
| **postgres** | postgres:16-alpine | Primary data store |
| **redis** | redis:7-alpine | Celery broker + cache |
| **elasticsearch** | ES 8.15.0 | Full-text search + correlation |
| **api** | Custom (Python 3.12) | FastAPI + Gunicorn |
| **worker** | Same as api | Celery + Beat scheduler |
| **frontend** | Custom (Node 20 + Nginx) | React SPA + reverse proxy |

All services run within Docker Compose. The frontend Nginx container is the only one exposed to the host (port 8080) and proxies `/api` requests to the API container.

---

## Technology Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | Python 3.12, FastAPI, SQLAlchemy 2, Pydantic v2, Alembic |
| **Frontend** | React 18, TypeScript, Vite, Tailwind CSS, TanStack Query, Recharts |
| **Database** | PostgreSQL 16 |
| **Search** | Elasticsearch 8.15 |
| **Queue** | Celery with Redis broker |
| **Auth** | JWT + API keys, bcrypt, Fernet encryption |
| **Containers** | Docker, Docker Compose |

---

## Configuration

### Environment Variables

Copy `.env.example` to `.env` and configure:

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SECRET_KEY` | Yes | — | JWT signing key (use `openssl rand -hex 32`) |
| `POSTGRES_PASSWORD` | Yes | — | PostgreSQL password |
| `FEED_ENCRYPTION_KEY` | No | `change-me-...` | Fernet key for encrypting feed credentials |
| `ADMIN_PASSWORD` | No | `admin` | Initial admin user password |
| `POSTGRES_USER` | No | `cti` | PostgreSQL username |
| `POSTGRES_DB` | No | `cti` | PostgreSQL database name |
| `LOG_LEVEL` | No | `INFO` | Logging level |
| `ENVIRONMENT` | No | `production` | `development` or `production` |

### Feed Configuration

Feeds can be added through the UI (Settings > Feeds > Add Feed). Each feed supports:

- **Schedule:** Cron expression for polling interval
- **Default Confidence:** 0-100 score reflecting source reliability
- **Default TTL:** Days until observables from this feed expire
- **Authentication:** Bearer token, API key, or basic auth (encrypted at rest)

Pre-configured feed presets are available for common threat intel sources.

---

## Development

### Local Setup (without Docker)

```bash
# Backend
uv sync                                    # Install Python dependencies
uv run alembic upgrade head                # Run database migrations
uv run fastapi dev src/cti/main.py         # Start API server (port 8000)
uv run celery -A cti.worker worker -l info -B  # Start Celery worker

# Frontend
cd frontend && npm install                 # Install frontend dependencies
npm run dev                                # Start dev server (port 5173)
```

Requires PostgreSQL, Redis, and Elasticsearch running locally (or via `docker compose up -d postgres redis elasticsearch`).

### Testing

```bash
uv run pytest                              # Backend tests
uv run ruff check .                        # Lint
uv run ruff format --check .               # Format check
uv run mypy src/                           # Type check

cd frontend
npx tsc --noEmit                           # Frontend type check
npx eslint src/                            # Frontend lint
npx vite build                             # Build verification
```

### Database Migrations

```bash
# Create a new migration
uv run alembic revision --autogenerate -m "description"

# Apply migrations
uv run alembic upgrade head

# Apply inside Docker
docker compose exec api alembic upgrade head
```

### Project Structure

```
src/cti/
├── main.py              # FastAPI application with lifespan
├── worker.py            # Celery tasks (feed ingestion, enrichment, reports)
├── api/v1/              # API route handlers
├── core/                # Config, database, security, dependencies
├── models/              # SQLAlchemy ORM models
├── schemas/             # Pydantic request/response schemas
├── services/            # Business logic layer
├── feeds/               # Feed connector implementations
├── enrichment/          # External enrichment providers
├── sso/                 # SSO provider implementations
└── templates/           # Jinja2 report templates

frontend/src/
├── api/                 # API client modules
├── components/          # React components (ui, layout, feeds, dashboard)
├── hooks/               # Custom React hooks
├── pages/               # Page components
├── contexts/            # Auth and toast contexts
└── types/               # TypeScript interfaces
```

---

## API

The API is served at `/api/v1/` with JWT or API key authentication.

### Key Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/auth/login` | Get JWT tokens |
| `GET` | `/api/v1/observables` | List observables (paginated, filterable) |
| `POST` | `/api/v1/observables` | Create observable |
| `GET` | `/api/v1/search` | Elasticsearch full-text search |
| `GET` | `/api/v1/feeds` | List configured feeds |
| `POST` | `/api/v1/feeds/{id}/trigger` | Trigger feed ingestion |
| `POST` | `/api/v1/enrichment/{id}/enrich` | Enrich an observable |
| `GET` | `/api/v1/dashboard/stats` | Platform statistics |
| `GET` | `/api/v1/graph/{type}/{id}` | Entity relationship graph |
| `POST` | `/api/v1/reports` | Generate a report |
| `POST` | `/api/v1/export/stix` | Export as STIX bundle |

### Authentication

```bash
# Get a JWT token
TOKEN=$(curl -s -X POST http://localhost:8080/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin"}' | jq -r .access_token)

# Use the token
curl -H "Authorization: Bearer $TOKEN" http://localhost:8080/api/v1/observables

# Or use an API key (generated in Settings)
curl -H "X-API-Key: your-api-key" http://localhost:8080/api/v1/observables
```

---

## Security

- Feed credentials encrypted at rest with Fernet symmetric encryption
- JWT access tokens expire in 30 minutes, refresh tokens in 7 days
- Role-based access control: Admin > Analyst > Read-only
- API key authentication for programmatic access
- All passwords hashed with bcrypt
- CI pipeline includes: Bandit SAST, pip-audit, npm audit, Trivy container scanning, TruffleHog secrets detection
- PostgreSQL bound to localhost only (not exposed to network)
- Elasticsearch and Redis are internal-only (no host port binding)
- Non-root container users

---

## Troubleshooting

**API container fails to start:**
```bash
docker compose logs api --tail 50      # Check for migration or startup errors
```

**Feeds not running on schedule:**
```bash
docker compose logs worker --tail 50   # Look for "Checking scheduled feeds" messages
```

**Search returns no results:**
```bash
# Trigger a full reindex
curl -X POST http://localhost:8080/api/v1/search/reindex \
  -H "Authorization: Bearer $TOKEN"
```

**Reset everything:**
```bash
docker compose down -v                 # Remove containers AND volumes
docker compose up -d --build           # Fresh start with empty database
```

---

## License

This project is proprietary. All rights reserved.

---

<p align="center">
  Built with FastAPI, React, and a lot of threat data.
</p>
