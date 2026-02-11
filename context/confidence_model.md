# Confidence Model -- Scoring and Lifecycle

## Overview

Every observable in EmergentCTI has a `confidence_score` (0-100 integer) representing how confident the platform is that the observable is a genuine threat indicator. This score is influenced by three mechanisms: feed defaults, enrichment updates, and lifecycle decay.

---

## Score Sources

### 1. Schema Default

When an observable is created without an explicit confidence score, the Pydantic schema default applies:

```python
confidence_score: int = Field(default=50, ge=0, le=100)
```

This is a neutral starting point, meaning "no strong signal either way."

### 2. Per-Feed Defaults

Each feed has a `default_confidence` in its `config` JSONB column. When a feed connector creates `ObservableCreate` instances, it sets `confidence_score` to the feed's default:

| Feed | Default Confidence | Rationale |
|------|--------------------|-----------|
| AbuseIPDB | 90 | Curated community reports with built-in scoring |
| OpenPhish | 80 | Verified phishing URLs |
| URLhaus | 75 | Community-submitted, moderate curation |
| Emerging Threats | 70 | Broad ruleset, some false positives |
| Blocklist.de | 65 | Automated honeypot data, no manual curation |
| Tor Exit Nodes | 30 | Legitimate privacy tool, not inherently malicious |

### 3. Enrichment Updates

After enrichment, the confidence score is updated using a weighted average. See "Enrichment Confidence Update" below.

---

## Upsert Semantics -- Multi-Source MAX

When the same observable is reported by multiple feeds, the upsert uses `func.greatest()` to keep the highest confidence score:

```python
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy import func

stmt = insert(Observable).values(
    type=obs_type,
    value=obs_value,
    confidence_score=feed_confidence,
    last_seen=func.now(),
)
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

### Example

1. Blocklist.de reports IP `1.2.3.4` with confidence=65
2. AbuseIPDB reports the same IP with confidence=90
3. After upsert: `confidence_score = greatest(65, 90) = 90`

This ensures that the highest-quality source determines the floor. The score can only increase through feed upserts (never decrease).

---

## Enrichment Confidence Update

After an enrichment provider returns data, the `confidence_service.py` module computes a new score using a weighted average:

### Formula

```
new_score = (existing_score * 0.4) + (provider_score * 0.6)
```

- **60% weight** for the enrichment provider (external intelligence is considered more authoritative)
- **40% weight** for the existing score (preserves feed-contributed context)
- Result is clamped to `[0, 100]`

### Implementation

```python
# src/cti/services/confidence_service.py
async def update_observable_confidence(
    db: AsyncSession,
    observable_id: uuid.UUID,
    provider_score: int,
) -> None:
    result = await db.execute(
        select(Observable.confidence_score).where(Observable.id == observable_id)
    )
    current = result.scalar_one_or_none()
    if current is None:
        return

    new_score = int(current * 0.4 + provider_score * 0.6)
    new_score = max(0, min(100, new_score))

    await db.execute(
        update(Observable)
        .where(Observable.id == observable_id)
        .values(confidence_score=new_score, updated_at=datetime.now(UTC))
    )
```

### Provider-Specific Score Extraction

The `compute_provider_confidence()` function extracts scores from raw provider data:

| Provider | Extraction Logic | Score Range |
|----------|-----------------|-------------|
| **AbuseIPDB** | `result_data["abuseConfidenceScore"]` | 0-100 (direct) |
| **VirusTotal** | `malicious / total * 100` from `last_analysis_stats` | 0-100 (computed) |
| **URLScan** | `result_data["score"]` or 85 if `malicious=true` | 0-100 or fixed 85 |
| **GreyNoise** | Classification map: malicious=85, benign=15, unknown=50 | 15, 50, or 85 |
| **Shodan** | `50 + (len(vulns) * 10)`, capped at 100 | 50-100 |

### Enrichment Examples

**Example 1: AbuseIPDB confirms malicious IP**
- IP arrives from Blocklist.de: confidence=65
- AbuseIPDB returns abuseConfidenceScore=92
- New score: `(65 * 0.4) + (92 * 0.6) = 26 + 55.2 = 81`

**Example 2: GreyNoise says benign**
- IP arrives from Emerging Threats: confidence=70
- GreyNoise classifies as "benign" (score=15)
- New score: `(70 * 0.4) + (15 * 0.6) = 28 + 9 = 37`

**Example 3: Multiple enrichments**
- IP starts at confidence=65 (Blocklist.de)
- AbuseIPDB enrichment: `(65 * 0.4) + (92 * 0.6) = 81`
- Shodan enrichment (3 vulns, score=80): `(81 * 0.4) + (80 * 0.6) = 32.4 + 48 = 80`
- Final confidence: 80

---

## Lifecycle Decay

Observables that are not refreshed by any feed become stale over time. The lifecycle decay mechanism gradually reduces confidence to prevent outdated indicators from generating false alerts.

### Decay Parameters

| Parameter | Value | Config Key |
|-----------|-------|------------|
| Stale threshold | 30 days since `last_seen` | `confidence.stale_threshold_days` |
| Decay rate | -5 points per week | `confidence.decay_rate_per_week` |
| Decay floor | 10 (minimum score) | `confidence.decay_floor` |
| Check interval | Every 3600 seconds | `lifecycle.check_interval_seconds` |

### Decay Logic

```
if (now - last_seen) > stale_threshold_days:
    weeks_stale = (now - last_seen - stale_threshold_days) / 7
    decayed_score = max(
        decay_floor,
        confidence_score - (decay_rate_per_week * weeks_stale)
    )
```

### Decay Example

An IP with confidence=80 and `last_seen` 45 days ago:
- Stale for: 45 - 30 = 15 days = ~2.14 weeks
- Decay: 80 - (5 * 2.14) = 80 - 10.7 = 69 (rounded to 69)

After 60 days (30 days stale):
- Decay: 80 - (5 * 4.28) = 80 - 21.4 = 59

After 120 days (90 days stale, ~12.8 weeks):
- Decay: 80 - (5 * 12.8) = 80 - 64 = 16

After 150 days (~17.1 weeks stale):
- Calculated: 80 - (5 * 17.1) = 80 - 85.5 = -5.5
- Clamped to floor: 10

### Refresh Resets Decay

When a feed re-reports an observable, `last_seen` is updated to `now()`, resetting the decay clock. The confidence score is also subject to `func.greatest()` upsert, potentially increasing it.

---

## Score Interpretation Guide

| Range | Meaning | Recommended Action |
|-------|---------|-------------------|
| 90-100 | Very high confidence, confirmed malicious | Block, alert, investigate |
| 70-89 | High confidence, likely malicious | Alert, investigate, consider blocking |
| 50-69 | Moderate confidence, suspicious | Monitor, enrich for more data |
| 30-49 | Low confidence, possibly benign | Watchlist only, do not alert |
| 10-29 | Very low confidence, likely benign or stale | Informational, consider expiration |
| 0-9 | No useful signal | Candidate for removal |

---

## Configuration

All confidence parameters are configurable in `args/defaults.yaml`:

```yaml
confidence:
  schema_default: 50
  decay_rate_per_week: 5
  decay_floor: 10
  stale_threshold_days: 30
  enrichment_weight_provider: 0.6
  enrichment_weight_existing: 0.4
```

---

## Related Files

- **Implementation:** `src/cti/services/confidence_service.py`
- **Observable model:** `src/cti/models/observable.py` (confidence_score column)
- **Schema:** `src/cti/schemas/observable.py` (default=50, ge=0, le=100)
- **Feed sources:** `context/feed_sources.md`
- **Args:** `args/defaults.yaml`
