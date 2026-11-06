#!/usr/bin/env python3
"""Evaluate dependency-audit scanner output against the project severity policy.

Called by ``scripts/audit-deps.sh``; see ``docs/security/dependency-audit.md``.
Stdlib only, so it runs on a bare CI runner.

Exit codes:
    0  clean per policy
    1  policy violation (finding at/above the scope's fail level, or a bad
       exception such as an expired one)
    2  the audit could not be evaluated (scanner/network/parse failure,
       invalid configuration). Never reported as clean.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
from dataclasses import dataclass, field
from typing import Any

EXIT_CLEAN = 0
EXIT_VIOLATION = 1
EXIT_ERROR = 2

LEVELS = ["low", "moderate", "high", "critical"]
RANK = {name: i for i, name in enumerate(LEVELS)}
SCOPES = ("runtime", "tooling")
EXCEPTION_FIELDS = (
    "id",
    "package",
    "scope",
    "severity",
    "reason",
    "mitigation",
    "owner",
    "expires",
)
GHSA_RE = re.compile(r"GHSA(-[0-9a-z]{4}){3}", re.IGNORECASE)


class AuditError(Exception):
    """The audit cannot be evaluated (exit 2)."""


@dataclass
class Finding:
    ecosystem: str
    scope: str
    package: str
    version: str
    id: str
    aliases: frozenset[str]
    severity: str  # one of LEVELS or "unknown"
    title: str = ""
    excepted_by: dict[str, Any] | None = None

    @property
    def key(self) -> tuple[str, str]:
        return (self.id.upper(), norm_package(self.package))

    def matches_id(self, ident: str) -> bool:
        ident = ident.upper()
        return ident == self.id.upper() or ident in {a.upper() for a in self.aliases}


@dataclass
class Source:
    ecosystem: str  # e.g. "frontend", "backend"
    scope: str  # runtime | tooling
    fmt: str  # npm | osv
    path: str
    rc: int
    findings: list[Finding] = field(default_factory=list)
    error: str | None = None


@dataclass
class Policy:
    fail_level: dict[str, str | None]  # scope -> level or None (never fail)
    unknown_as: str
    max_exception_days: int
    today: dt.date


def norm_package(name: str) -> str:
    # PEP 503 normalisation is harmless for npm names (they are lowercase).
    return re.sub(r"[-_.]+", "-", name).lower()


def norm_severity(raw: Any) -> str:
    if raw is None:
        return "unknown"
    s = str(raw).strip().lower()
    if s == "medium":
        s = "moderate"
    if s in RANK:
        return s
    try:
        score = float(s)
    except ValueError:
        return "unknown"
    if score >= 9.0:
        return "critical"
    if score >= 7.0:
        return "high"
    if score >= 4.0:
        return "moderate"
    if score > 0.0:
        return "low"
    return "unknown"


def load_json(path: str) -> Any:
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError as exc:
        raise AuditError(f"scanner output missing: {path}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise AuditError(f"scanner output is not valid JSON ({path}): {exc}") from exc


# --------------------------------------------------------------------------- parsers


def parse_npm(data: Any, rc: int, ecosystem: str, scope: str) -> list[Finding]:
    """Parse ``npm audit --json`` (auditReportVersion 2).

    npm exits 1 both when vulnerabilities exist and when the audit request
    failed, so validity is decided from the JSON shape, not the exit code.
    """
    if rc not in (0, 1):
        raise AuditError(f"npm audit exited {rc}")
    if not isinstance(data, dict):
        raise AuditError("npm audit output is not a JSON object")
    if "error" in data:
        err = data.get("error") or {}
        detail = data.get("message") or (err.get("summary") if isinstance(err, dict) else err)
        raise AuditError(f"npm audit reported an error: {detail or err}")
    counts = (data.get("metadata") or {}).get("vulnerabilities")
    vulns = data.get("vulnerabilities")
    if not isinstance(counts, dict) or not isinstance(vulns, dict):
        raise AuditError("npm audit output lacks metadata.vulnerabilities / vulnerabilities")
    if rc == 0 and vulns:
        raise AuditError("npm audit exited 0 but reported vulnerabilities (inconsistent output)")

    found: dict[tuple[str, str], Finding] = {}
    for entry in vulns.values():
        for via in entry.get("via") or []:
            if not isinstance(via, dict):
                continue  # string = "vulnerable because of dependency X"; X has its own entry
            url = str(via.get("url") or "")
            m = GHSA_RE.search(url)
            # Canonical GHSA form: upper-case prefix, lower-case body (as on github.com/advisories).
            ident = "GHSA" + m.group(0)[4:].lower() if m else f"NPM-{via.get('source')}"
            f = Finding(
                ecosystem=ecosystem,
                scope=scope,
                package=str(via.get("name") or entry.get("name")),
                version=str(via.get("range") or ""),
                id=ident,
                aliases=frozenset({ident}),
                severity=norm_severity(via.get("severity")),
                title=str(via.get("title") or ""),
            )
            found.setdefault(f.key, f)

    # Mirror parse_osv: a "vulnerable" result we could not extract anything from
    # must not be mistaken for a clean one (e.g. only string `via` entries, or a
    # report format we do not understand).
    total = counts.get("total")
    if rc == 1 and not found:
        raise AuditError(
            "npm audit exited 1 but no advisories could be extracted (inconsistent output)"
        )
    if isinstance(total, int) and total > 0 and not found:
        raise AuditError(
            f"npm audit metadata reports {total} vulnerable package(s) "
            "but no advisories could be extracted"
        )
    return list(found.values())


def parse_osv(data: Any, rc: int, ecosystem: str, scope: str) -> list[Finding]:
    """Parse ``osv-scanner scan source --format json``.

    osv-scanner exits 0 (no vulns) or 1 (vulns). Anything else -- notably 127
    when api.osv.dev is unreachable -- is a failure even though it still
    prints a well-formed, empty ``{"results": []}``.
    """
    if rc not in (0, 1):
        raise AuditError(f"osv-scanner exited {rc} (scanner/network failure)")
    if not isinstance(data, dict) or not isinstance(data.get("results"), list):
        raise AuditError("osv-scanner output lacks a results list")

    out: list[Finding] = []
    for result in data["results"]:
        for pkg in result.get("packages") or []:
            info = pkg.get("package") or {}
            by_id = {v.get("id"): v for v in pkg.get("vulnerabilities") or []}
            for group in pkg.get("groups") or []:
                ids = [str(i) for i in group.get("ids") or []]
                aliases = frozenset(ids + [str(a) for a in group.get("aliases") or []])
                primary = next(
                    (i for i in ids if i.upper().startswith("GHSA-")), ids[0] if ids else ""
                )
                if not primary:
                    raise AuditError(f"osv-scanner group without ids for {info.get('name')}")
                severity = norm_severity(group.get("max_severity") or None)
                if severity == "unknown":
                    for i in ids:
                        db = (by_id.get(i) or {}).get("database_specific") or {}
                        if norm_severity(db.get("severity")) != "unknown":
                            severity = norm_severity(db.get("severity"))
                            break
                summary = next((by_id[i].get("summary", "") for i in ids if i in by_id), "")
                out.append(
                    Finding(
                        ecosystem=ecosystem,
                        scope=scope,
                        package=str(info.get("name")),
                        version=str(info.get("version") or ""),
                        id=primary,
                        aliases=aliases,
                        severity=severity,
                        title=str(summary),
                    )
                )
    if rc == 1 and not out:
        raise AuditError(
            "osv-scanner exited 1 but reported no vulnerabilities (inconsistent output)"
        )
    if rc == 0 and out:
        raise AuditError("osv-scanner exited 0 but reported vulnerabilities (inconsistent output)")
    return out


PARSERS = {"npm": parse_npm, "osv": parse_osv}


# --------------------------------------------------------------------------- exceptions


def load_exceptions(path: str) -> list[dict[str, Any]]:
    if not os.path.exists(path):
        raise AuditError(f"exceptions file not found: {path}")
    data = load_json(path)
    if not isinstance(data, list):
        raise AuditError(f"{path}: expected a JSON array")
    for n, exc in enumerate(data):
        where = f"{path}[{n}]"
        if not isinstance(exc, dict):
            raise AuditError(f"{where}: expected an object")
        missing = [k for k in EXCEPTION_FIELDS if not str(exc.get(k) or "").strip()]
        if missing:
            raise AuditError(f"{where}: missing/empty field(s): {', '.join(missing)}")
        if exc["scope"] not in SCOPES:
            raise AuditError(f"{where}: scope must be one of {SCOPES}")
        if str(exc["severity"]).lower() not in [*LEVELS, "unknown"]:
            raise AuditError(f"{where}: severity must be one of {[*LEVELS, 'unknown']}")
        try:
            exc["_expires"] = dt.date.fromisoformat(str(exc["expires"]))
        except ValueError as e:
            raise AuditError(f"{where}: expires must be YYYY-MM-DD") from e
    return data


def check_exceptions(exceptions: list[dict[str, Any]], policy: Policy) -> list[str]:
    """Return policy violations for exceptions that are expired or too long-lived."""
    problems = []
    limit = policy.today + dt.timedelta(days=policy.max_exception_days)
    for exc in exceptions:
        label = f"{exc['id']} / {exc['package']} / {exc['scope']} (owner {exc['owner']})"
        if exc["_expires"] < policy.today:
            problems.append(
                f"exception EXPIRED on {exc['expires']}: {label} "
                "-- fix the finding or renew with fresh justification"
            )
        elif exc["_expires"] > limit:
            problems.append(
                f"exception expires {exc['expires']}, more than "
                f"{policy.max_exception_days} days out: {label}"
            )
    return problems


def apply_exceptions(
    findings: list[Finding], exceptions: list[dict[str, Any]], policy: Policy
) -> tuple[set[int], list[str]]:
    """Mark findings covered by a *valid* exception.

    An exception matches only the exact advisory id (or alias), package, scope
    *and* severity, so an exception filed as "low" can never hide a finding
    that is (or was re-scored as) "high".

    Returns the indices of exceptions used and notes about near-misses whose
    severity differed.
    """
    used: set[int] = set()
    mismatches: list[str] = []
    for f in findings:
        for n, exc in enumerate(exceptions):
            if exc["_expires"] < policy.today:
                continue  # expired exceptions never suppress anything
            if not (
                exc["scope"] == f.scope
                and norm_package(exc["package"]) == norm_package(f.package)
                and f.matches_id(str(exc["id"]))
            ):
                continue
            if str(exc["severity"]).lower() != f.severity:
                mismatches.append(
                    f"exception {exc['id']} / {exc['package']} / {exc['scope']} is for severity "
                    f"{exc['severity']!r} but the finding is {f.severity!r}; not applied"
                )
                continue
            f.excepted_by = exc
            used.add(n)
            break
    return used, mismatches


# --------------------------------------------------------------------------- evaluation


def effective_severity(f: Finding, policy: Policy) -> str:
    return policy.unknown_as if f.severity == "unknown" else f.severity


def is_failing(f: Finding, policy: Policy) -> bool:
    level = policy.fail_level.get(f.scope)
    if level is None or f.excepted_by is not None:
        return False
    return RANK[effective_severity(f, policy)] >= RANK[level]


def subtract_runtime(sources: list[Source]) -> None:
    """Tooling scope = full tree minus what the same ecosystem already reports as runtime."""
    runtime_keys = {
        (s.ecosystem, f.key)
        for s in sources
        if s.scope == "runtime" and s.error is None
        for f in s.findings
    }
    for s in sources:
        if s.scope == "tooling":
            s.findings = [f for f in s.findings if (s.ecosystem, f.key) not in runtime_keys]


def evaluate(
    sources: list[Source], exceptions: list[dict[str, Any]], policy: Policy, out=sys.stdout
) -> int:
    for s in sources:
        try:
            s.findings = PARSERS[s.fmt](load_json(s.path), s.rc, s.ecosystem, s.scope)
        except AuditError as exc:
            s.error = str(exc)
    subtract_runtime(sources)

    all_findings = [f for s in sources for f in s.findings]
    exception_problems = check_exceptions(exceptions, policy)
    used, mismatches = apply_exceptions(all_findings, exceptions, policy)

    w = out.write
    w("\nDependency audit summary\n")

    def row(scope: str, source: str, cells: list[Any], level: str, result: str) -> str:
        nums = " ".join(f"{c:>4}" for c in cells)
        return f"{scope:<8} {source:<10} {nums}  {level:<9} {result}\n"

    header = row(
        "scope", "source", ["crit", "high", "mod", "low", "unk", "exc"], "fails on", "result"
    )
    w(header)
    w("-" * (len(header) - 1) + "\n")
    for s in sources:
        level = policy.fail_level.get(s.scope) or "never"
        if s.error:
            w(row(s.scope, s.ecosystem, ["-"] * 6, level, "SCANNER FAILURE"))
            continue
        active = [f for f in s.findings if f.excepted_by is None]
        counts = {lvl: sum(1 for f in active if f.severity == lvl) for lvl in [*LEVELS, "unknown"]}
        excepted = sum(1 for f in s.findings if f.excepted_by is not None)
        failing = any(is_failing(f, policy) for f in s.findings)
        result = "FAIL" if failing else ("report" if active else "clean")
        cells = [counts[k] for k in ("critical", "high", "moderate", "low", "unknown")]
        w(row(s.scope, s.ecosystem, [*cells, excepted], level, result))

    order = sorted(
        all_findings,
        key=lambda f: (f.scope, -RANK[effective_severity(f, policy)], f.ecosystem, f.package, f.id),
    )
    if order:
        w("\nFindings\n")
        for f in order:
            tag = "EXCEPTED" if f.excepted_by else ("FAIL" if is_failing(f, policy) else "report")
            sev = f.severity if f.severity != "unknown" else f"unknown->{policy.unknown_as}"
            ver = f" {f.version}" if f.version else ""
            w(f"  [{tag:<8}] {f.scope:<7} {f.ecosystem:<8} {f.package}{ver}  {f.id}  {sev}")
            w(f"  {f.title[:70]}\n")
            if f.excepted_by:
                exc = f.excepted_by
                w(f"             exception owner={exc['owner']} expires={exc['expires']}\n")

    errors = [s for s in sources if s.error]
    for s in errors:
        w(f"\nSCANNER FAILURE ({s.scope}/{s.ecosystem}, {s.path}): {s.error}\n")
    for problem in exception_problems:
        w(f"\nPOLICY: {problem}\n")
    for note in mismatches:
        w(f"\nnote: {note}\n")
    for n, exc in enumerate(exceptions):
        if n not in used and exc["_expires"] >= policy.today:
            label = f"{exc['id']} / {exc['package']} / {exc['scope']}"
            w(f"\nnote: exception {label} matched nothing; consider removing it\n")

    violations = any(is_failing(f, policy) for f in all_findings) or bool(exception_problems)
    if errors:
        w("\nRESULT: AUDIT INCOMPLETE -- scanner failure; this is NOT a clean result (exit 2)\n")
        return EXIT_ERROR
    if violations:
        w("\nRESULT: POLICY VIOLATION (exit 1)\n")
        return EXIT_VIOLATION
    w("\nRESULT: clean per policy (exit 0)\n")
    return EXIT_CLEAN


# --------------------------------------------------------------------------- CLI


def parse_level(name: str, value: str) -> str | None:
    value = value.strip().lower()
    if value == "none":
        return None
    value = "moderate" if value == "medium" else value
    if value not in RANK:
        raise AuditError(f"{name}={value!r}: expected one of {[*LEVELS, 'none']}")
    return value


def policy_from_env(env: dict[str, str]) -> Policy:
    unknown = parse_level("AUDIT_UNKNOWN_SEVERITY", env.get("AUDIT_UNKNOWN_SEVERITY", "high"))
    if unknown is None:
        raise AuditError("AUDIT_UNKNOWN_SEVERITY cannot be 'none'")
    try:
        max_days = int(env.get("AUDIT_EXCEPTION_MAX_DAYS", "90"))
        today = (
            dt.date.fromisoformat(env["AUDIT_TODAY"]) if env.get("AUDIT_TODAY") else dt.date.today()
        )
    except ValueError as exc:
        raise AuditError(f"invalid AUDIT_EXCEPTION_MAX_DAYS / AUDIT_TODAY: {exc}") from exc
    return Policy(
        fail_level={
            "runtime": parse_level(
                "AUDIT_RUNTIME_FAIL_LEVEL", env.get("AUDIT_RUNTIME_FAIL_LEVEL", "high")
            ),
            "tooling": parse_level(
                "AUDIT_TOOLING_FAIL_LEVEL", env.get("AUDIT_TOOLING_FAIL_LEVEL", "critical")
            ),
        },
        unknown_as=unknown,
        max_exception_days=max_days,
        today=today,
    )


def parse_source(spec: str) -> Source:
    # ECOSYSTEM:SCOPE:FORMAT:RC:PATH  (path last so it may contain ':')
    parts = spec.split(":", 4)
    if len(parts) != 5:
        raise AuditError(f"bad --source {spec!r}; expected ECOSYSTEM:SCOPE:FORMAT:RC:PATH")
    eco, scope, fmt, rc, path = parts
    if scope not in SCOPES or fmt not in PARSERS:
        raise AuditError(f"bad --source {spec!r}: scope in {SCOPES}, format in {tuple(PARSERS)}")
    try:
        return Source(eco, scope, fmt, path, int(rc))
    except ValueError as exc:
        raise AuditError(f"bad --source {spec!r}: RC must be an integer") from exc


def main(argv: list[str] | None = None, env: dict[str, str] | None = None) -> int:
    env = dict(os.environ) if env is None else env
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "--source", action="append", required=True, help="ECOSYSTEM:SCOPE:FORMAT:RC:PATH"
    )
    ap.add_argument(
        "--exceptions", default=env.get("AUDIT_EXCEPTIONS_FILE", "security/audit-exceptions.json")
    )
    args = ap.parse_args(argv)
    try:
        policy = policy_from_env(env)
        sources = [parse_source(s) for s in args.source]
        exceptions = load_exceptions(args.exceptions)
        return evaluate(sources, exceptions, policy)
    except AuditError as exc:
        print(f"audit-deps: ERROR: {exc}\nRESULT: AUDIT INCOMPLETE (exit 2)", file=sys.stderr)
        return EXIT_ERROR


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except BaseException as exc:  # any crash must be exit 2, never 1 ("violation") or 0
        print(f"audit-deps: internal error: {exc!r}", file=sys.stderr)
        sys.exit(EXIT_ERROR)
