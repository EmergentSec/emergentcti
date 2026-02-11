# Feed Ingestion -- Add and Configure Threat Intel Feeds

## Objective

Add, configure, and manage threat intelligence feed connectors that normalize external data into the EmergentCTI internal schema. Each feed produces observables with confidence scores, categories, and metadata that are upserted into PostgreSQL and indexed in Elasticsearch.

---

## Feed Connector Architecture

All feed connectors inherit from `BaseFeedConnector` defined in `src/cti/feeds/base.py`.

### Four Feed Types

| Type | Class | Location | Use Case |
|------|-------|----------|----------|
| `api` | `APIFeedConnector` | `src/cti/feeds/api_connector.py` | REST API polling (AbuseIPDB, etc.) |
| `taxii` | `TAXIIFeedConnector` | `src/cti/feeds/taxii_connector.py` | STIX/TAXII 2.x protocol |
| `file` | `FileFeedConnector` | `src/cti/feeds/file_connector.py` | CSV, JSON, STIX bundles |
| `scraper` | `ScraperFeedConnector` | `src/cti/feeds/scraper_connector.py` | Web scraping threat blogs |

### Connector Interface

Every connector must implement three abstract methods:

```python
class BaseFeedConnector(ABC):
    async def connect(self) -> None:
        """Validate connectivity and credentials."""

    async def fetch(self) -> Any:
        """Retrieve raw data from the source."""

    async def normalize(self, raw_data: Any) -> list[ObservableCreate]:
        """Transform raw data into ObservableCreate instances."""
```

The `ingest()` template method orchestrates the pipeline: `connect -> fetch -> normalize -> FeedResult`.

### FeedResult Dataclass

Returned by `ingest()`, contains:
- `observables` -- list of `ObservableCreate` schemas
- `started_at` / `completed_at` -- timing metadata
- `raw_record_count` -- number of raw records fetched
- `errors` -- list of error messages (empty if success)
- `success` -- property, True if no errors

---

## Feed Configuration Schema

Each feed is stored in the `feeds` table with these key columns:

| Column | Type | Description |
|--------|------|-------------|
| `name` | String(256) | Unique feed name |
| `feed_type` | Enum | api, taxii, file, scraper |
| `url` | String(2048) | Feed source URL |
| `config` | JSONB | Feed-specific configuration |
| `schedule_cron` | String(64) | Cron expression for scheduling |
| `auth_config_encrypted` | LargeBinary | Fernet-encrypted auth credentials |
| `default_ttl_days` | Integer | Observable expiration TTL |
| `enabled` | Boolean | Whether the feed is active |

### Config JSONB Fields

The `config` JSONB column supports these keys (varies by feed):

```json
{
  "default_confidence": 75,
  "observable_types": ["ip-addr", "domain-name"],
  "default_category": "malware",
  "parser": "csv_ip_list",
  "headers": {"Accept": "text/plain"},
  "timeout": 30
}
```

---

## Confidence Model

Each feed has a `default_confidence` in its `config` JSONB column (0-100 scale):

| Feed | Default Confidence | Rationale |
|------|--------------------|-----------|
| AbuseIPDB | 90 | Curated community reports with scoring |
| OpenPhish | 80 | Verified phishing URLs |
| URLhaus | 75 | Community-submitted, moderate curation |
| Emerging Threats | 70 | Broad ruleset, some false positives |
| Blocklist.de | 65 | Automated honeypot data |
| Tor Exit Nodes | 30 | Legitimate privacy use, not inherently malicious |

### Upsert Semantics

When an observable already exists (matched by `type + value` composite key), the upsert uses `func.greatest()` to keep the highest confidence score across all sources:

```python
stmt = insert(Observable).values(...)
stmt = stmt.on_conflict_do_update(
    constraint="uq_observable_type_value",
    set_={
        "confidence_score": func.greatest(
            Observable.confidence_score,
            stmt.excluded.confidence_score,
        ),
        "last_seen": func.now(),
    },
)
```

This ensures that if AbuseIPDB (confidence=90) and Blocklist.de (confidence=65) both report the same IP, the observable retains confidence=90.

---

## Step-by-Step: Adding a New Feed

### 1. Create the Feed Record

Via API:
```bash
curl -X POST http://localhost:8080/api/v1/feeds \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "MyNewFeed",
    "feed_type": "api",
    "url": "https://api.example.com/indicators",
    "schedule_cron": "0 */4 * * *",
    "config": {
      "default_confidence": 70,
      "observable_types": ["ip-addr", "domain-name"],
      "default_category": "malware"
    }
  }'
```

### 2. Implement the Connector (if custom)

Create a new file in `src/cti/feeds/`:

```python
from cti.feeds.base import BaseFeedConnector, FeedResult
from cti.schemas.observable import ObservableCreate

class MyNewFeedConnector(BaseFeedConnector):
    async def connect(self) -> None:
        # Validate API key, test endpoint
        ...

    async def fetch(self) -> Any:
        # HTTP GET with auth headers
        ...

    async def normalize(self, raw_data: Any) -> list[ObservableCreate]:
        # Parse response, create ObservableCreate instances
        ...
```

### 3. Register the Connector

Add the connector to the feed type dispatch in `src/cti/services/feed_service.py` so the Celery worker can instantiate it.

### 4. Test the Feed

```bash
# Run feed ingestion manually via API
curl -X POST http://localhost:8080/api/v1/feeds/{feed_id}/run \
  -H "Authorization: Bearer $TOKEN"

# Check feed run status
curl http://localhost:8080/api/v1/feeds/{feed_id}/runs \
  -H "Authorization: Bearer $TOKEN"
```

### 5. Verify Observables

```bash
# Search for newly ingested observables
curl "http://localhost:8080/api/v1/observables?source={feed_id}" \
  -H "Authorization: Bearer $TOKEN"
```

---

## Edge Cases and Error Handling

### Rate Limits
- Respect provider rate limits (check response headers for `X-RateLimit-Remaining`)
- Feed config supports `max_retries` (default: 3) and `retry_delay_seconds` (default: 60)
- On 429 response, back off exponentially

### Auth Failures
- Feed credentials are Fernet-encrypted at rest (`auth_config_encrypted` column)
- On 401/403, mark the FeedRun as `failure` with descriptive error_message
- Do not retry auth failures; alert the admin

### Malformed Data
- The `normalize()` method must catch parsing errors per-record
- Log and skip malformed records rather than failing the entire run
- Track `raw_record_count` vs `observable_count` to measure data loss

### Duplicate Handling
- Observables are deduplicated by `type + value` composite unique key
- ON CONFLICT upsert updates `last_seen`, keeps `func.greatest()` confidence
- The `observable_sources` M:N table tracks which feeds contributed each observable

---

## Tools

| Tool | Purpose |
|------|---------|
| `tools/test/run_tests.sh` | Run full test suite after adding a feed |
| `tools/deploy/docker_deploy.sh` | Rebuild and deploy after code changes |

---

## Celery Task Flow

1. Celery beat triggers `ingest_feed` task per schedule_cron
2. Worker instantiates the appropriate `BaseFeedConnector` subclass
3. Connector runs `ingest()` pipeline: connect -> fetch -> normalize
4. Worker iterates over `FeedResult.observables` and upserts each into PostgreSQL
5. Worker syncs new/updated observables to Elasticsearch index
6. Worker creates `FeedRun` record with status, count, and any errors
7. If `EnrichmentConfig.auto_enrich` is enabled, dispatches enrichment tasks

---

## Related Files

- **Model:** `src/cti/models/feed.py` (Feed, FeedRun)
- **Schema:** `src/cti/schemas/feed.py`
- **Base:** `src/cti/feeds/base.py` (BaseFeedConnector, FeedResult)
- **Connectors:** `src/cti/feeds/api_connector.py`, `taxii_connector.py`, `file_connector.py`, `scraper_connector.py`
- **Service:** `src/cti/services/feed_service.py`
- **Routes:** `src/cti/api/v1/feeds.py`
- **Context:** `context/feed_sources.md`, `context/confidence_model.md`
