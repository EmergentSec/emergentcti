#!/usr/bin/env bash
set -euo pipefail
# Build and deploy all Docker Compose application services
# Usage: bash tools/deploy/docker_deploy.sh [service...]

cd "$(git rev-parse --show-toplevel)"

SERVICES="${@:-frontend api worker}"
echo "Building and deploying: $SERVICES"
docker compose up -d --build $SERVICES
echo "Deploy complete. Services:"
docker compose ps
