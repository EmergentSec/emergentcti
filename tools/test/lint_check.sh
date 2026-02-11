#!/usr/bin/env bash
set -euo pipefail
# Run all linters and type checkers
# Usage: bash tools/test/lint_check.sh

cd "$(git rev-parse --show-toplevel)"

echo "=== Ruff Lint ==="
uv run ruff check .

echo ""
echo "=== Ruff Format Check ==="
uv run ruff format --check .

echo ""
echo "=== Frontend ESLint ==="
cd frontend
npx eslint src/

echo ""
echo "=== TypeScript Check ==="
npx tsc --noEmit

echo ""
echo "All lint checks passed."
