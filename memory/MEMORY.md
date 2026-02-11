# Persistent Memory

> This file contains curated long-term facts, preferences, and context that persist across sessions.

## Project Identity

- Platform: EmergentCTI -- Cyber Threat Intelligence platform
- Stack: FastAPI + React + PostgreSQL + Elasticsearch + Redis + Celery
- Framework: GOTCHA (Goals, Orchestration, Tools, Context, Hardprompts, Args)
- Deployment: Docker Compose (6 services on port 8080)

## Key Facts

- 6 configured feeds: AbuseIPDB, Emerging Threats, Blocklist.de, Tor Exit Nodes, OpenPhish, URLhaus
- 5 enrichment providers: VirusTotal, AbuseIPDB, Shodan, GreyNoise, URLScan
- Auth: JWT + API keys, RBAC (admin > analyst > readonly)
- Default admin: admin/admin (change in production)
- 13+ alembic migrations
- Feed credentials encrypted with Fernet symmetric encryption

## Learned Behaviors

- Always check tools/manifest.md before creating new scripts
- Follow GOTCHA framework: Goals, Orchestration, Tools, Context, Hardprompts, Args
- Rebuild Docker containers after code changes: `docker compose up -d --build api worker frontend`
- Run `alembic upgrade head` after creating migrations

## Current Projects

- Wave 5: Intelligence Pipeline, Graph Explorer, Reporting
- Confidence scoring fix: func.greatest() for multi-source MAX
- GOTCHA framework integration

---

*Last updated: 2026-02-11*
