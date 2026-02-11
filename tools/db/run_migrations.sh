#!/usr/bin/env bash
set -euo pipefail
# Run alembic database migrations inside the API container
# Usage: bash tools/db/run_migrations.sh

cd "$(git rev-parse --show-toplevel)"
echo "Running database migrations..."
docker compose exec -T api alembic upgrade head
echo "Migrations complete."
