#!/usr/bin/env bash
set -euo pipefail
# Run security scanning tools
# Usage: bash tools/security/scan.sh

cd "$(git rev-parse --show-toplevel)"

echo "=== Bandit SAST ==="
uv run bandit -r src/ -c pyproject.toml || true

echo ""
echo "=== pip-audit ==="
uv run pip-audit || true

echo ""
echo "=== npm audit ==="
cd frontend
npm audit || true

echo ""
echo "Security scan complete."
