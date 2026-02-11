#!/usr/bin/env bash
set -euo pipefail
# Verify all EmergentCTI services are healthy
# Usage: bash tools/deploy/health_check.sh

cd "$(git rev-parse --show-toplevel)"

echo "Checking service health..."

# PostgreSQL
if docker compose exec -T postgres pg_isready -U cti > /dev/null 2>&1; then
  echo "[OK] PostgreSQL"
else
  echo "[FAIL] PostgreSQL"
fi

# Redis
if docker compose exec -T redis redis-cli ping 2>/dev/null | grep -q PONG; then
  echo "[OK] Redis"
else
  echo "[FAIL] Redis"
fi

# Elasticsearch
if curl -sf http://localhost:9200/_cluster/health > /dev/null 2>&1; then
  echo "[OK] Elasticsearch"
else
  echo "[FAIL] Elasticsearch"
fi

# API
if curl -sf http://localhost:8080/api/v1/dashboard/stats > /dev/null 2>&1; then
  echo "[OK] API (via nginx)"
else
  echo "[FAIL] API"
fi

# Frontend
if curl -sf http://localhost:8080/ > /dev/null 2>&1; then
  echo "[OK] Frontend"
else
  echo "[FAIL] Frontend"
fi

echo "Health check complete."
