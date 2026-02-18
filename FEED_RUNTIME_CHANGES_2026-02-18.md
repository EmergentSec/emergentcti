# Feed Runtime Changes (2026-02-18)

## Scope

These updates were applied to the **running Docker environment** (PostgreSQL feed records), not to core Python source code.

- Target environment: `docker compose` stack for `emergentcti`
- Data store changed: `feeds` and `feed_runs` tables (runtime data)
- Code changes made by me: none

## What I Changed

### 1. Recreated/updated feed records in Postgres

Configured the following feeds as enabled:

1. `AbuseIPDB` (`api`)
2. `Blocklist.de` (`file`)
3. `Emerging Threats` (`file`)
4. `OpenPhish` (`file`)
5. `Tor Exit Nodes` (`file`)
6. `URLhaus` (`file`)

### 2. Updated free-feed parser config (non-API)

For plain-text list feeds, I set file parsing so they ingest correctly:

- `format: "csv"`
- `csv.has_header: false`
- `csv.column_map.value: 0`
- `csv.default_type`: `ip-addr` or `url` depending on feed
- `csv.comment_char: "#"`

This was applied to:

- `Blocklist.de` (`ip-addr`)
- `Emerging Threats` (`ip-addr`)
- `Tor Exit Nodes` (`ip-addr`)
- `OpenPhish` (`url`)
- `URLhaus` (`url`)

### 3. Switched URLhaus to free non-auth source

- Old URL: `https://urlhaus-api.abuse.ch/v1/urls/recent/` (returning 401 in this run)
- New URL: `https://urlhaus.abuse.ch/downloads/text_recent/`
- Connector type used: `file`

### 4. Updated AbuseIPDB request shape

Configured to match your provided usage pattern:

- URL: `https://api.abuseipdb.com/api/v2/blacklist?confidenceMinimum=90`
- Method: `GET`
- Headers include: `Accept: application/json`
- Auth header mapping: `Key` (stored as `api_key_header`)

Also restored mapping fields needed for normalization:

- `results_path: "data"`
- `field_map.value: "ipAddress"`
- `field_map.confidence_score: "abuseConfidenceScore"`
- `field_map.last_seen: "lastReportedAt"`
- `default_type: "ip-addr"`

## Verification Results Observed

After triggering runs, feed ingestion counts were:

- `Blocklist.de`: `24083`
- `Emerging Threats`: `447`
- `OpenPhish`: `300`
- `Tor Exit Nodes`: `1225`
- `URLhaus`: `20708`
- `AbuseIPDB`: `0` (subsequent requests hit API limit/rate issues in this session)

## Important Notes

1. These are **runtime DB/config updates**, not committed code changes.
2. If Docker volumes are removed/reset, these feed records/configs will be lost unless re-applied.
3. During this session, worker logs also showed Celery Beat schedule-file permission errors (`celerybeat-schedule`), which is separate from feed parsing config.

