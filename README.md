# EmergentCTI

Lightweight Cyber Threat Intelligence platform for IOC feed aggregation and export, with a web dashboard and user authentication.

## Quick Start

```bash
cp .env.example .env
```

Edit `.env` and set the required values (the stack will not start until these are set):

- `POSTGRES_PASSWORD` — database password
- `REDIS_PASSWORD` — Redis password
- `FEED_ENCRYPTION_KEY` — Fernet key used to encrypt stored feed credentials. Generate one with:
  ```bash
  python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
  ```
- `JWT_SECRET_KEY` — **required** when `ENVIRONMENT=production` (the default). The API refuses to start without it. Generate one with:
  ```bash
  python -c "import secrets; print(secrets.token_urlsafe(32))"
  ```
- `ADMIN_PASSWORD` — password for the initial `admin` user, created on first boot. Set it or you won't be able to log into the web UI.

Then start the stack:

```bash
docker compose up -d
```

**Web UI:** http://localhost:8080 — log in as `admin` with the `ADMIN_PASSWORD` you set.

**API key** (for programmatic access) is auto-generated on first boot. Grab it from the logs — it's shown only once:

```bash
docker compose logs api | grep -A1 "INITIAL API KEY"
```

## Features

- **Web Dashboard** — Aggregation health, 14-day ingestion trend, observable-type breakdown, feed status, and confidence distribution; dark/light themes with a toggle
- **User Authentication** — JWT session login for the web UI with `admin` / `user` roles; `X-API-Key` auth for programmatic access
- **Feed Aggregation** — Ingest from 13 pre-configured feeds (AbuseIPDB, abuse.ch, CINSscore, DShield, etc.) plus custom feeds
- **Blocklist Export** — Plain-text exports for direct firewall integration (pfSense, PAN EDLs, etc.) and full JSON export
- **Confidence Scoring** — Dual-mode scoring with native feed scores and linear time decay; native-vs-decayed surfaced per observable
- **Observable Types** — IP addresses, domains, URLs, file hashes, emails, command lines

## API

Endpoints authenticate with an `X-API-Key` header (programmatic access) **or** a JWT session cookie (web UI). `GET /api/v1/health` is public.

| Endpoint | Description |
|----------|-------------|
| `GET /api/v1/observables` | Search/filter observables |
| `GET /api/v1/observables/{id}` | Observable detail with per-source attribution |
| `GET /api/v1/feeds` | List feeds |
| `POST /api/v1/feeds/{id}/trigger` | Run a feed now (admin) |
| `GET /api/v1/export/blocklist/{type}` | Plain-text blocklist |
| `GET /api/v1/export/json` · `GET /api/v1/export/text` | JSON / plain-text export |
| `GET /api/v1/stats` | Dashboard stats |
| `GET /api/v1/settings/api-keys` · `/users` · `/config` | API keys, users, read-only config (admin) |

## Development

Backend — run the API and tests with [uv](https://docs.astral.sh/uv/):

```bash
uv run --extra dev pytest
```

Frontend — the web UI lives in `frontend/`:

```bash
cd frontend
npm install
npm run dev      # Vite dev server on :5173 (proxies /api to the backend)
npm run test     # Vitest
```
