#!/usr/bin/env bash
# Repeatable dependency audit for EmergentCTI. See docs/security/dependency-audit.md.
#
# Scopes audited:
#   runtime  frontend: npm audit --omit=dev   backend: osv-scanner on `uv export --no-dev`
#   tooling  frontend: npm audit (full tree)  backend: osv-scanner on `uv export --extra dev`
#            (tooling = full tree minus findings already reported as runtime)
#
# Exit codes: 0 clean per policy | 1 policy violation | 2 audit could not be
# completed (scanner, network, parse or configuration failure -- never "clean").
#
# Environment (defaults in brackets):
#   AUDIT_RUNTIME_FAIL_LEVEL [high]      fail when a runtime finding is >= this (low|moderate|high|critical|none)
#   AUDIT_TOOLING_FAIL_LEVEL [critical]  same for tooling; lower findings are reported only
#   AUDIT_UNKNOWN_SEVERITY   [high]      severity assumed when an advisory has none
#   AUDIT_EXCEPTIONS_FILE    [security/audit-exceptions.json]
#   AUDIT_EXCEPTION_MAX_DAYS [90]        exceptions may not expire further out than this
#   AUDIT_OUTPUT_DIR         [temp dir]  keep raw scanner JSON here (e.g. for CI artifacts)
set -euo pipefail

# Any unexpected failure (missing tool, uv export error, ...) is exit 2, never 1.
trap 'rc=$?; echo "audit-deps: unexpected failure (exit $rc) at line $LINENO: $BASH_COMMAND" >&2; echo "RESULT: AUDIT INCOMPLETE (exit 2)" >&2; exit 2' ERR

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

for tool in npm uv osv-scanner python3; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    echo "audit-deps: required tool '$tool' not found on PATH (see docs/security/dependency-audit.md)" >&2
    echo "RESULT: AUDIT INCOMPLETE (exit 2)" >&2
    exit 2
  fi
done

if [[ -n "${AUDIT_OUTPUT_DIR:-}" ]]; then
  OUT="$AUDIT_OUTPUT_DIR"
  mkdir -p "$OUT"
else
  OUT="$(mktemp -d)"
  trap 'rm -rf "$OUT"' EXIT
fi
export AUDIT_EXCEPTIONS_FILE="${AUDIT_EXCEPTIONS_FILE:-$ROOT/security/audit-exceptions.json}"

# run_scanner OUTFILE CMD... -> echoes the scanner's exit code; stdout goes to OUTFILE.
# Scanner exit codes are interpreted by audit_policy.py, together with the JSON shape.
run_scanner() {
  local outfile="$1"; shift
  local rc=0
  "$@" >"$outfile" 2>"$outfile.stderr" || rc=$?
  echo "$rc"
}

# --audit-level=info: npm exits 1 for any finding regardless of user/global
# npmrc, so the evaluator's exit-code/finding consistency checks are reliable.
echo "audit-deps: frontend runtime (npm audit --omit=dev)" >&2
fe_rt_rc=$(cd frontend && run_scanner "$OUT/frontend-runtime.json" npm audit --omit=dev --audit-level=info --json)
echo "audit-deps: frontend full tree (npm audit)" >&2
fe_all_rc=$(cd frontend && run_scanner "$OUT/frontend-all.json" npm audit --audit-level=info --json)

echo "audit-deps: backend export from uv.lock" >&2
# --frozen: audit exactly what uv.lock pins; never re-resolve here.
uv export --frozen --no-dev --no-hashes --no-emit-project --quiet -o "$OUT/backend-runtime.txt"
uv export --frozen --extra dev --no-hashes --no-emit-project --quiet -o "$OUT/backend-all.txt"

# --no-resolve: the export is already the complete pinned closure.
osv() { osv-scanner scan source --no-resolve --verbosity error --format json -L "requirements.txt:$1"; }
echo "audit-deps: backend runtime (osv-scanner)" >&2
be_rt_rc=$(run_scanner "$OUT/backend-runtime.json" osv "$OUT/backend-runtime.txt")
echo "audit-deps: backend runtime + dev (osv-scanner)" >&2
be_all_rc=$(run_scanner "$OUT/backend-all.json" osv "$OUT/backend-all.txt")

rc=0
python3 "$ROOT/scripts/audit_policy.py" \
  --source "frontend:runtime:npm:$fe_rt_rc:$OUT/frontend-runtime.json" \
  --source "backend:runtime:osv:$be_rt_rc:$OUT/backend-runtime.json" \
  --source "frontend:tooling:npm:$fe_all_rc:$OUT/frontend-all.json" \
  --source "backend:tooling:osv:$be_all_rc:$OUT/backend-all.json" || rc=$?

case "$rc" in
  0 | 1 | 2) ;;
  *) echo "audit-deps: policy evaluator exited $rc; treating as failure" >&2; rc=2 ;;
esac
if [[ "$rc" == 2 ]]; then
  for f in "$OUT"/*.stderr; do
    if [[ -s "$f" ]]; then
      echo "--- $(basename "$f") (tail)" >&2
      tail -n 5 "$f" >&2
    fi
  done
fi
exit "$rc"
