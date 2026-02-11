# Enrichment -- Enrich Observables with External Provider Data

## Objective

Enrich observables with threat intelligence data from external providers. The enrichment pipeline queries providers for additional context (reputation scores, geolocation, open ports, malware analysis) and updates observable confidence scores using a weighted average model.

---

## Enrichment Providers

Five providers are supported, each implemented as a `BaseEnrichmentProvider` subclass in `src/cti/enrichment/`:

| Provider | File | Supported Types | Rate Limit | Score Extraction |
|----------|------|-----------------|------------|------------------|
| VirusTotal | `virustotal.py` | file-hash, url, domain-name, ip-addr | 4/min (free) | malicious/total ratio from `last_analysis_stats` |
| AbuseIPDB | `abuseipdb.py` | ip-addr | 1000/day | `abuseConfidenceScore` (0-100 direct) |
| Shodan | `shodan.py` | ip-addr | 1/sec | 50 + (vuln_count * 10), capped at 100 |
| GreyNoise | `greynoise.py` | ip-addr | 50/day (community) | classification map: malicious=85, benign=15, unknown=50 |
| URLScan | `urlscan.py` | url, domain-name | 60/min | `score` field or malicious flag (85) |

### Provider Interface

All providers implement `BaseEnrichmentProvider` from `src/cti/enrichment/base.py`:

```python
class BaseEnrichmentProvider(ABC):
    name: ClassVar[str]
    supported_types: ClassVar[list[str]]

    @abstractmethod
    async def enrich(
        self, observable_type: str, observable_value: str, api_key: str
    ) -> EnrichmentResult:
        """Run enrichment and return result."""
```

### EnrichmentResult Dataclass

```python
@dataclass
class EnrichmentResult:
    provider: str
    success: bool
    data: dict          # Raw provider response
    error: str | None   # Error message if failed
    summary: str | None  # Human-readable summary
```

---

## Auto-Enrichment Pipeline

### Trigger

Auto-enrichment is triggered after feed ingestion when `EnrichmentConfig.auto_enrich = True` for a given provider.

### Flow

1. Feed ingestion completes, producing new/updated observables
2. Celery worker checks which `EnrichmentConfig` records have `auto_enrich = True`
3. For each enabled provider, filter observables by `supported_types`
4. Dispatch `enrich_observable` Celery tasks (one per observable-provider pair)
5. Each task calls the provider's `enrich()` method
6. On success, store `EnrichmentRun` record with `result_data` and `summary`
7. Call `confidence_service.update_observable_confidence()` with extracted score

### Cooldown

Auto-enrichment respects a cooldown period (default: 24 hours) to avoid re-enriching recently enriched observables. Check `EnrichmentRun.created_at` for the most recent run of each provider-observable pair.

---

## Confidence Update Model

The confidence score update uses a weighted average defined in `src/cti/services/confidence_service.py`:

### Formula

```
new_score = (existing_score * 0.4) + (provider_score * 0.6)
```

- **60% weight** goes to the enrichment provider score (external intelligence)
- **40% weight** goes to the existing score (preserves feed-contributed score)
- Result is clamped to 0-100

### Provider-Specific Score Extraction

The `compute_provider_confidence()` function in `confidence_service.py` extracts scores:

| Provider | Extraction Logic |
|----------|-----------------|
| AbuseIPDB | `result_data["abuseConfidenceScore"]` -- direct 0-100 score |
| VirusTotal | `malicious / total * 100` from `last_analysis_stats` |
| URLScan | `result_data["score"]` or 85 if `malicious` flag set |
| GreyNoise | Classification map: `{"malicious": 85, "benign": 15, "unknown": 50}` |
| Shodan | `50 + (len(vulns) * 10)`, capped at 100 |

### Example

An IP address arrives from Blocklist.de (feed confidence=65). Later, AbuseIPDB enrichment returns `abuseConfidenceScore=92`:

```
new_score = (65 * 0.4) + (92 * 0.6) = 26 + 55.2 = 81
```

The observable confidence updates from 65 to 81.

---

## Rate Limiting

### Per-Provider Configuration

Each `EnrichmentConfig` record has a `rate_limit_per_minute` column:

| Provider | Default Rate Limit |
|----------|--------------------|
| VirusTotal | 4/min (free tier) |
| AbuseIPDB | 16/min (~1000/day) |
| Shodan | 1/sec (60/min) |
| GreyNoise | 1/min (community) |
| URLScan | 60/min |

### Implementation

- Celery tasks use a dispatch delay (`args/defaults.yaml`: `rate_limit_between_dispatches_seconds: 1`)
- Before each API call, check remaining quota via response headers
- On 429 Too Many Requests, log the error and skip (do not retry immediately)
- Track failed enrichments in `EnrichmentRun` with `status=failure`

---

## Step-by-Step: Configuring a New Provider

### 1. Configure via API

```bash
curl -X POST http://localhost:8080/api/v1/enrichment/config \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "provider_name": "virustotal",
    "enabled": true,
    "auto_enrich": true,
    "api_key": "your-vt-api-key",
    "priority": 1,
    "rate_limit_per_minute": 4
  }'
```

### 2. Manual Enrichment

```bash
curl -X POST http://localhost:8080/api/v1/enrichment/enrich/{observable_id} \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"providers": ["virustotal", "abuseipdb"]}'
```

### 3. Check Enrichment Results

```bash
curl http://localhost:8080/api/v1/enrichment/runs?observable_id={id} \
  -H "Authorization: Bearer $TOKEN"
```

---

## EnrichmentConfig Model

Stored in the `enrichment_configs` table:

| Column | Type | Description |
|--------|------|-------------|
| `provider_name` | String(100) | Unique provider identifier |
| `enabled` | Boolean | Whether the provider is active |
| `auto_enrich` | Boolean | Trigger after feed ingestion |
| `api_key_encrypted` | LargeBinary | Fernet-encrypted API key |
| `config` | JSONB | Provider-specific settings |
| `priority` | Integer | Execution order (lower = first) |
| `rate_limit_per_minute` | Integer | Max API calls per minute |

## EnrichmentRun Model

Stored in the `enrichment_runs` table:

| Column | Type | Description |
|--------|------|-------------|
| `observable_id` | UUID (FK) | Observable being enriched |
| `provider_name` | String(100) | Which provider ran |
| `status` | Enum | pending, running, success, failure |
| `result_data` | JSONB | Raw provider response |
| `summary` | Text | Human-readable summary |
| `error_message` | Text | Error details if failed |
| `triggered_by` | UUID (FK) | User who triggered (null for auto) |

---

## Edge Cases

- **Provider down:** Mark `EnrichmentRun` as failure, do not update confidence
- **No score extractable:** `compute_provider_confidence()` returns None; skip confidence update
- **Observable deleted during enrichment:** Check existence before writing results
- **API key rotation:** Re-encrypt via `FEED_ENCRYPTION_KEY` Fernet key; old runs unaffected
- **Bulk enrichment:** Dispatch with staggered delays to respect rate limits

---

## Tools

| Tool | Purpose |
|------|---------|
| `tools/test/run_tests.sh` | Run full test suite after enrichment changes |

---

## Related Files

- **Base:** `src/cti/enrichment/base.py` (BaseEnrichmentProvider, EnrichmentResult)
- **Providers:** `src/cti/enrichment/virustotal.py`, `abuseipdb.py`, `shodan.py`, `greynoise.py`, `urlscan.py`
- **Registry:** `src/cti/enrichment/registry.py`
- **Models:** `src/cti/models/enrichment.py` (EnrichmentConfig, EnrichmentRun)
- **Schema:** `src/cti/schemas/enrichment.py`
- **Confidence:** `src/cti/services/confidence_service.py`
- **Routes:** `src/cti/api/v1/enrichment.py`
- **Context:** `context/confidence_model.md`
