# Architecture -- System Design and Component Interaction

## Overview

EmergentCTI is a multi-service cyber threat intelligence platform deployed via Docker Compose. The system follows a layered architecture with clear separation between API routing, business logic, data access, and asynchronous task processing.

---

## Docker Services (6 Containers)

```
                                    Port 8080
                                       |
                              ┌────────▼────────┐
                              │    frontend      │
                              │  (React + Vite)  │
                              │  nginx :8080     │
                              └────────┬─────────┘
                                       |
                              ┌────────▼────────┐
                              │      api         │
                              │  (FastAPI +      │
                              │   Gunicorn)      │
                              │  :8000 internal  │
                              └──┬─────┬─────┬──┘
                                 |     |     |
               ┌─────────────────┘     |     └──────────────────┐
               │                       │                        │
      ┌────────▼────────┐   ┌─────────▼─────────┐   ┌─────────▼─────────┐
      │   PostgreSQL     │   │      Redis         │   │  Elasticsearch    │
      │   :5432          │   │      :6379         │   │  :9200            │
      │   (primary DB)   │   │   (cache + broker) │   │  (search index)   │
      └──────────────────┘   └─────────┬──────────┘   └───────────────────┘
                                       │
                              ┌────────▼────────┐
                              │     worker       │
                              │  (Celery +       │
                              │   Celery Beat)   │
                              └──────────────────┘
```

### Service Details

| Service | Image | Purpose | Resources |
|---------|-------|---------|-----------|
| **postgres** | postgres:16-alpine | Primary data store for all models | 512M RAM |
| **redis** | redis:7-alpine | Celery broker + result backend, API caching | 256M RAM |
| **elasticsearch** | elasticsearch:8.15.0 | Full-text search and observable correlation | 1G RAM |
| **api** | Custom (Dockerfile) | FastAPI application serving the REST API | 512M RAM |
| **worker** | Custom (Dockerfile) | Celery worker + beat scheduler for async tasks | 512M RAM |
| **frontend** | Custom (frontend/Dockerfile) | React SPA served via nginx | 128M RAM |

---

## API Layer Architecture

The API follows a three-layer pattern: **Routes -> Services -> Models**.

### Layer 1: Routes (`src/cti/api/v1/`)

Routes handle HTTP concerns only:
- Parse request bodies via Pydantic schemas
- Authenticate and authorize via FastAPI dependencies
- Delegate all business logic to the service layer
- Return Pydantic response schemas

```
src/cti/api/v1/
  router.py            # Aggregates all sub-routers
  observables.py       # Observable CRUD endpoints
  feeds.py             # Feed management and triggering
  enrichment.py        # Enrichment configuration and execution
  search.py            # Elasticsearch-powered search
  auth.py              # Login, token refresh, API key management
  sso.py               # SSO callback endpoints
  alerts.py            # Alert rule configuration
  attack.py            # MITRE ATT&CK technique lookup
  relationships.py     # Observable relationship management
  correlations.py      # Correlation rule management
  threat_actors.py     # Threat actor tracking
  campaigns.py         # Campaign management
  dashboard.py         # Dashboard statistics
  audit.py             # Audit log access
  saved_searches.py    # Saved search management
  webhooks.py          # Webhook configuration
  import_.py           # STIX/CSV import
```

### Layer 2: Services (`src/cti/services/`)

Services contain all business logic:
- Database queries via SQLAlchemy async sessions
- Data validation beyond schema-level checks
- Cross-entity operations (e.g., upsert observable + link to feed)
- Elasticsearch index synchronization
- Celery task dispatching

```
src/cti/services/
  feed_service.py          # Feed CRUD, auth encryption/decryption, ingestion
  confidence_service.py    # Score computation and updates
  auth_service.py          # User auth, JWT generation, password hashing
  user_service.py          # User management
  search_service.py        # Elasticsearch queries
  alert_service.py         # Alert rule evaluation
  notification_service.py  # Email/webhook notifications
  attack_service.py        # ATT&CK data seeding and lookup
  correlation_service.py   # Correlation rule engine
  relationship_service.py  # Observable-to-observable links
  campaign_service.py      # Campaign tracking
  threat_actor_service.py  # Threat actor management
  dashboard_service.py     # Statistics aggregation
  audit_service.py         # Audit log recording
  export_service.py        # STIX/CSV export
  import_service.py        # STIX/CSV import
  saved_search_service.py  # Saved search persistence
  webhook_service.py       # Webhook dispatch
  note_service.py          # Observable notes
```

### Layer 3: Models (`src/cti/models/`)

SQLAlchemy ORM models define the database schema:

```
src/cti/models/
  base.py             # Base class, UUIDMixin, TimestampMixin
  observable.py       # Observable + ObservableType enum
  feed.py             # Feed + FeedRun + FeedType enum
  enrichment.py       # EnrichmentConfig + EnrichmentRun
  user.py             # User + Role enum
  tag.py              # Tag (M:N with Observable)
  alert.py            # AlertRule + AlertMatch
  relationship.py     # ObservableRelationship
  correlation.py      # CorrelationRule + CorrelationMatch
  attack.py           # ATTACKTechnique + ATTACKTactic
  campaign.py         # Campaign
  threat_actor.py     # ThreatActor
  audit_log.py        # AuditLog
  sso_config.py       # SSOProviderConfig
  saved_search.py     # SavedSearch
  note.py             # Note
```

---

## Feed Connector Pattern

Feed connectors are implemented using the Template Method pattern:

```
src/cti/feeds/
  base.py               # BaseFeedConnector (abstract) + FeedResult
  api_connector.py      # REST API polling
  taxii_connector.py    # STIX/TAXII 2.x protocol
  file_connector.py     # CSV, JSON, plaintext files
  scraper_connector.py  # Web scraping with custom parsers
```

### Ingestion Flow

```
Celery Beat (cron schedule)
    │
    ▼
ingest_feed task
    │
    ▼
FeedService.get_feed(feed_id)
    │
    ▼
Instantiate connector (based on feed_type)
    │
    ▼
connector.ingest()
    │
    ├── connect()     → Validate credentials
    ├── fetch()       → Retrieve raw data
    └── normalize()   → Parse into ObservableCreate list
    │
    ▼
FeedResult (observables, metadata, errors)
    │
    ▼
Upsert observables (ON CONFLICT with func.greatest)
    │
    ▼
Sync to Elasticsearch index
    │
    ▼
Record FeedRun (status, count, errors)
    │
    ▼
[If auto_enrich enabled] → Dispatch enrichment tasks
```

---

## Enrichment Pipeline

```
Trigger (manual or auto-enrich)
    │
    ▼
EnrichmentService.enrich_observable(observable_id, providers)
    │
    ▼
For each enabled provider:
    │
    ├── Check rate_limit_per_minute
    ├── Check cooldown (24h since last run)
    │
    ▼
provider.enrich(type, value, api_key)
    │
    ▼
EnrichmentResult (data, summary, success/error)
    │
    ▼
Store EnrichmentRun record
    │
    ▼
compute_provider_confidence(provider, result_data)
    │
    ▼
update_observable_confidence(db, observable_id, score)
    │ weighted average: 60% provider, 40% existing
    ▼
Updated observable.confidence_score
```

---

## Celery Task Architecture

The Celery worker handles all asynchronous processing:

| Task | Schedule | Description |
|------|----------|-------------|
| `ingest_feed` | Per-feed cron | Runs feed connector pipeline |
| `enrich_observable` | On-demand / auto | Calls enrichment provider |
| `evaluate_alerts` | After ingestion | Checks alert rules against new observables |
| `lifecycle_check` | Hourly | Decay stale confidence scores |
| `sync_elasticsearch` | After writes | Keep search index current |

### Worker Configuration

```bash
celery -A cti.worker worker -l info -B --concurrency=2
```

- `-B` enables Celery Beat (scheduler) in the same process
- `--concurrency=2` limits parallel task execution (memory constrained)
- Redis is both broker and result backend

---

## Authentication and Authorization

### Auth Methods

1. **JWT tokens** -- Primary auth for UI and API clients
   - Access token: 30 min expiry (`HS256` signed with `SECRET_KEY`)
   - Refresh token: 7 day expiry
   - Obtained via `POST /api/v1/auth/login`

2. **API keys** -- For programmatic access
   - Long-lived tokens associated with a user
   - Passed via `X-API-Key` header

3. **SSO** -- Enterprise single sign-on
   - Azure AD, Google Workspace, generic OIDC
   - Configured via environment variables
   - Auto-creates users with configurable default role

### RBAC Roles

| Role | Permissions |
|------|------------|
| `admin` | Full access: users, config, feeds, observables, system |
| `analyst` | Read/write observables, feeds, enrichment, reports |
| `readonly` | Read-only access to all data, no modifications |

---

## Data Flow Summary

```
External Sources                Internal Processing              User Access
─────────────────              ────────────────────             ────────────
  AbuseIPDB API  ──┐                                          ┌── Web UI (:8080)
  ET blocklist   ──┤           ┌───────────────┐               │
  Blocklist.de   ──┼──► Feed ──► PostgreSQL    ◄──── API ◄────┼── REST clients
  Tor exit list  ──┤   Ingest  │ (source of    │     Layer    │
  OpenPhish URLs ──┤           │  truth)       │              └── API keys
  URLhaus API    ──┘           └───────┬───────┘
                                       │
                                       ├──► Elasticsearch (search)
                                       │
                     Enrichment ◄──────┘
                     Pipeline          │
                         │             ▼
                  ┌──────┴──────┐   Alerts ──► Notifications
                  │ VirusTotal  │             (email, webhook)
                  │ AbuseIPDB   │
                  │ Shodan      │
                  │ GreyNoise   │
                  │ URLScan     │
                  └─────────────┘
```

---

## Key Design Decisions

1. **PostgreSQL as source of truth** -- All data lives in PostgreSQL. Elasticsearch is a read-optimized secondary index.
2. **Observable deduplication** -- Unique constraint on `(type, value)` with ON CONFLICT upsert prevents duplicates.
3. **Fernet encryption for credentials** -- Feed and enrichment API keys encrypted at rest using `FEED_ENCRYPTION_KEY`.
4. **Async-first** -- FastAPI with async SQLAlchemy sessions for non-blocking I/O.
5. **Celery for background work** -- Feed ingestion and enrichment are CPU/IO-bound tasks that run asynchronously.
6. **Pydantic v2 strict validation** -- All API inputs validated through Pydantic models before reaching business logic.

---

## Related Files

- **Entrypoint:** `src/cti/main.py`
- **Config:** `src/cti/core/config.py`
- **Docker:** `docker-compose.yml`, `Dockerfile`, `frontend/Dockerfile`
- **Feed sources:** `context/feed_sources.md`
- **Confidence:** `context/confidence_model.md`
- **Observable types:** `context/observable_types.md`
