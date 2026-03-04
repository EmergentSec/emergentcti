# EmergentCTI

Lightweight Cyber Threat Intelligence platform for IOC feed aggregation and export.

## Quick Start

```bash
cp .env.example .env
# Edit .env with your settings (at minimum set POSTGRES_PASSWORD and FEED_ENCRYPTION_KEY)
docker compose up -d
```

Check the API logs for your initial API key:
```bash
docker compose logs api | grep "API key"
```

Access the web UI at http://localhost:8080

## Features

- **Feed Aggregation** — Ingest from 13 pre-configured feeds (AbuseIPDB, abuse.ch, CINSscore, DShield, etc.) plus custom feeds
- **REST API** — Simple query and export API (no GraphQL)
- **Blocklist Export** — Plain text exports for direct FW integration (pfSense, PAN EDLs, etc.)
- **Confidence Scoring** — Dual-mode scoring with native feed scores and time decay
- **Observable Types** — IP addresses, domains, URLs, file hashes, emails, command lines

## API

All endpoints require an `X-API-Key` header (except `/api/v1/health`).

| Endpoint | Description |
|----------|-------------|
| `GET /api/v1/observables` | Search/filter observables |
| `GET /api/v1/feeds` | List feeds |
| `GET /api/v1/export/blocklist/{type}` | Plain text blocklist |
| `GET /api/v1/export/json` | JSON export |
| `GET /api/v1/stats` | Dashboard stats |

## Development

```bash
uv sync --all-extras
pytest
```
