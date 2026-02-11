# Deployment -- Deploy CTI Platform via Docker Compose

## Objective

Deploy the EmergentCTI platform as a multi-container Docker Compose application. The deployment consists of 6 services that must start in the correct order, run database migrations, seed initial data, and pass health checks before the platform is considered operational.

---

## Service Architecture

| Service | Image | Port | Memory Limit | Depends On |
|---------|-------|------|--------------|------------|
| postgres | postgres:16-alpine | 5432 (internal) | 512M | -- |
| redis | redis:7-alpine | 6379 (internal) | 256M | -- |
| elasticsearch | elasticsearch:8.15.0 | 9200 (internal) | 1G | -- |
| api | Custom (Dockerfile) | 8000 (internal) | 512M | postgres, redis, elasticsearch |
| worker | Custom (Dockerfile) | -- | 512M | postgres, redis, elasticsearch |
| frontend | Custom (frontend/Dockerfile) | 8080 (exposed) | 128M | api |

### Access Points

- **Frontend UI:** `http://localhost:8080`
- **API docs (dev only):** `http://localhost:8080/api/docs`
- **Health check:** `http://localhost:8080/api/v1/health`

---

## Environment Variables

The `.env` file must contain these required variables:

```bash
# Required (docker compose will fail without these)
POSTGRES_PASSWORD=<strong-password>
SECRET_KEY=<random-256-bit-key>

# Recommended to change from defaults
ADMIN_PASSWORD=<admin-login-password>       # default: admin
FEED_ENCRYPTION_KEY=<fernet-key>            # generate: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Optional overrides
POSTGRES_USER=cti                           # default: cti
POSTGRES_DB=cti                             # default: cti
ENVIRONMENT=production                      # default: production
LOG_LEVEL=INFO                              # default: INFO

# SSO (optional)
SSO_AZURE_AD_ENABLED=false
SSO_GOOGLE_ENABLED=false
SSO_OIDC_ENABLED=false
```

### Generating Secrets

```bash
# Generate SECRET_KEY
python -c "import secrets; print(secrets.token_hex(32))"

# Generate FEED_ENCRYPTION_KEY (Fernet)
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Generate POSTGRES_PASSWORD
python -c "import secrets; print(secrets.token_urlsafe(24))"
```

---

## Deployment Steps

### 1. Prepare Environment

```bash
cd /Users/funtime/git/cti
cp .env.example .env
# Edit .env with production values (see above)
```

### 2. Build and Start Services

```bash
# Build all images and start in detached mode
docker compose up -d --build

# Watch logs during startup
docker compose logs -f
```

### 3. Run Database Migrations

Migrations run automatically on API container startup via the command:
```
alembic upgrade head && gunicorn cti.main:app ...
```

If you need to run migrations manually:
```bash
docker compose exec api alembic upgrade head
```

### 4. Verify Startup

```bash
# Check all services are running
docker compose ps

# Expected output: all 6 services with status "Up" or "Up (healthy)"
```

### 5. Health Check Procedure

```bash
# API health
curl -s http://localhost:8080/api/v1/health | python -m json.tool
# Expected: {"status": "healthy", "version": "0.1.0"}

# PostgreSQL
docker compose exec postgres pg_isready -U cti
# Expected: accepting connections

# Redis
docker compose exec redis redis-cli ping
# Expected: PONG

# Elasticsearch
curl -s http://localhost:9200/_cluster/health | python -m json.tool
# Expected: status "yellow" or "green"

# Celery worker
docker compose exec worker celery -A cti.worker inspect ping
# Expected: pong response

# Frontend
curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/
# Expected: 200
```

---

## Post-Deployment Verification

### 1. Verify Login

1. Open `http://localhost:8080` in a browser
2. Log in with default credentials: `admin` / `admin` (or your `ADMIN_PASSWORD`)
3. Change the admin password immediately in production

### 2. Check Worker Logs

```bash
docker compose logs worker --tail=50
# Look for: "celery@<hostname> ready" and no error traces
```

### 3. Confirm Feeds Running

```bash
# List configured feeds via API
curl -s http://localhost:8080/api/v1/feeds \
  -H "Authorization: Bearer $TOKEN" | python -m json.tool

# Check feed run history
curl -s http://localhost:8080/api/v1/feeds/{feed_id}/runs \
  -H "Authorization: Bearer $TOKEN" | python -m json.tool
```

### 4. Verify MITRE ATT&CK Seeding

```bash
curl -s "http://localhost:8080/api/v1/attack/techniques?limit=5" \
  -H "Authorization: Bearer $TOKEN" | python -m json.tool
# Expected: list of ATT&CK techniques
```

---

## Updating the Deployment

### Code Changes (backend or worker)

```bash
docker compose up -d --build api worker
```

### Frontend Changes

```bash
docker compose up -d --build frontend
```

### Full Rebuild

```bash
docker compose up -d --build api worker frontend
```

### Database Migration After Model Changes

```bash
# Generate migration locally
uv run alembic revision --autogenerate -m "description of change"

# Apply in container
docker compose exec api alembic upgrade head

# Or rebuild to apply on startup
docker compose up -d --build api
```

---

## Troubleshooting

### Service Won't Start

```bash
# Check logs for the failing service
docker compose logs <service-name> --tail=100

# Common issues:
# - postgres: POSTGRES_PASSWORD not set in .env
# - api: Migration failure (check alembic output)
# - elasticsearch: vm.max_map_count too low (set to 262144)
# - frontend: API not healthy yet (depends_on condition)
```

### Elasticsearch Memory Error

```bash
# On Linux, increase virtual memory
sudo sysctl -w vm.max_map_count=262144

# Make permanent
echo "vm.max_map_count=262144" | sudo tee -a /etc/sysctl.conf
```

### Reset Everything

```bash
docker compose down -v    # Removes volumes (DATA LOSS)
docker compose up -d --build
```

---

## Resource Requirements

Minimum system requirements for the full stack:

| Resource | Minimum | Recommended |
|----------|---------|-------------|
| RAM | 4 GB | 8 GB |
| CPU | 2 cores | 4 cores |
| Disk | 10 GB | 50 GB |

---

## Tools

| Tool | Purpose |
|------|---------|
| `tools/deploy/docker_deploy.sh` | Automated build and deploy |
| `tools/deploy/health_check.sh` | Run all health checks |
| `tools/db/run_migrations.sh` | Run Alembic migrations in container |

---

## Related Files

- **Docker Compose:** `docker-compose.yml`
- **API Dockerfile:** `Dockerfile`
- **Frontend Dockerfile:** `frontend/Dockerfile`
- **Config:** `src/cti/core/config.py` (Settings class)
- **Environment:** `.env.example`
- **Context:** `context/architecture.md`
