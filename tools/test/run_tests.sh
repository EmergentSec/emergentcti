#!/usr/bin/env bash
set -euo pipefail
# Run full test suite: backend pytest + frontend type check + build
# Usage: bash tools/test/run_tests.sh

cd "$(git rev-parse --show-toplevel)"

echo "=== Backend Tests ==="
uv run pytest -x -q

echo ""
echo "=== Frontend Type Check ==="
cd frontend
npx tsc --noEmit

echo ""
echo "=== Frontend Build ==="
npx vite build

echo ""
echo "All tests passed."
