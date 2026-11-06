"""Offline tests for scripts/audit_policy.py and scripts/audit-deps.sh (issue #18).

No network: scanner output is fed from fixture JSON, and the shell test puts
fake ``npm``/``uv``/``osv-scanner`` executables first on PATH.
"""

from __future__ import annotations

import importlib.util
import io
import json
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("audit_policy", ROOT / "scripts" / "audit_policy.py")
assert SPEC and SPEC.loader
ap = importlib.util.module_from_spec(SPEC)
sys.modules["audit_policy"] = ap  # dataclasses resolve annotations via sys.modules
SPEC.loader.exec_module(ap)

TODAY = "2026-11-05"


# --------------------------------------------------------------------------- fixtures


def npm_report(*advisories: tuple[str, str, str]) -> dict:
    """advisories: (package, GHSA id, severity)."""
    vulns: dict = {}
    for pkg, ghsa, sev in advisories:
        entry = vulns.setdefault(pkg, {"name": pkg, "severity": sev, "isDirect": True, "via": []})
        entry["via"].append(
            {
                "source": 1,
                "name": pkg,
                "title": f"{pkg} issue",
                "url": f"https://github.com/advisories/{ghsa}",
                "severity": sev,
                "range": "<9.9.9",
            }
        )
    counts = {k: 0 for k in ("info", "low", "moderate", "high", "critical")}
    for entry in vulns.values():
        counts[entry["severity"]] += 1
    counts["total"] = len(vulns)
    return {
        "auditReportVersion": 2,
        "vulnerabilities": vulns,
        "metadata": {"vulnerabilities": counts},
    }


NPM_ERROR = {
    "message": "request to http://127.0.0.1:9/-/npm/v1/security/advisories/bulk failed",
    "error": {"summary": "", "detail": ""},
}
OSV_EMPTY = {"results": []}
NPM_STRING_VIA_ONLY = {
    "auditReportVersion": 2,
    "vulnerabilities": {"react-router-dom": {"name": "react-router-dom", "via": ["react-router"]}},
    "metadata": {"vulnerabilities": {"moderate": 1, "total": 1}},
}
NPM_TOTAL_WITHOUT_ADVISORIES = {
    "auditReportVersion": 2,
    "vulnerabilities": {},
    "metadata": {"vulnerabilities": {"high": 2, "total": 2}},
}


def osv_report(pkg: str, version: str, ids: list[str], aliases: list[str], max_sev: str) -> dict:
    return {
        "results": [
            {
                "source": {"path": "x.txt", "type": "lockfile"},
                "packages": [
                    {
                        "package": {"name": pkg, "version": version, "ecosystem": "PyPI"},
                        "vulnerabilities": [{"id": i, "summary": f"{pkg} bug"} for i in ids],
                        "groups": [{"ids": ids, "aliases": aliases, "max_severity": max_sev}],
                    }
                ],
            }
        ]
    }


def write(tmp_path: Path, name: str, data: object) -> str:
    p = tmp_path / name
    p.write_text(data if isinstance(data, str) else json.dumps(data))
    return str(p)


def run(tmp_path: Path, sources: list[tuple[str, str, str, int, object]], exceptions=None, **env):
    """Evaluate (ecosystem, scope, fmt, scanner rc, json-or-raw-text) sources."""
    srcs = [
        ap.Source(eco, scope, fmt, write(tmp_path, f"s{n}.json", data), rc)
        for n, (eco, scope, fmt, rc, data) in enumerate(sources)
    ]
    excs = ap.load_exceptions(write(tmp_path, "exceptions.json", exceptions or []))
    out = io.StringIO()
    code = ap.evaluate(srcs, excs, ap.policy_from_env({"AUDIT_TODAY": TODAY, **env}), out=out)
    return code, out.getvalue()


def exception(**overrides) -> dict:
    exc = {
        "id": "GHSA-aaaa-bbbb-cccc",
        "package": "axios",
        "scope": "runtime",
        "severity": "high",
        "reason": "not reachable: server-side adapter unused in browser bundle",
        "mitigation": "upgrade tracked in follow-up",
        "owner": "security@example.invalid",
        "expires": "2026-12-01",
    }
    exc.update(overrides)
    return exc


HIGH_AXIOS = npm_report(("axios", "GHSA-aaaa-bbbb-cccc", "high"))


# --------------------------------------------------------------------------- policy


def test_clean_everywhere_exits_0(tmp_path):
    rc, out = run(
        tmp_path,
        [
            ("frontend", "runtime", "npm", 0, npm_report()),
            ("backend", "runtime", "osv", 0, OSV_EMPTY),
        ],
    )
    assert rc == 0
    assert "clean per policy" in out


def test_runtime_high_fails(tmp_path):
    rc, out = run(tmp_path, [("frontend", "runtime", "npm", 1, HIGH_AXIOS)])
    assert rc == 1
    assert "GHSA-aaaa-bbbb-cccc" in out and "POLICY VIOLATION" in out


def test_runtime_moderate_is_reported_not_failed(tmp_path):
    rc, out = run(
        tmp_path,
        [("frontend", "runtime", "npm", 1, npm_report(("x", "GHSA-2222-3333-4444", "moderate")))],
    )
    assert rc == 0
    assert "[report" in out


def test_tooling_high_reports_but_critical_fails(tmp_path):
    high = npm_report(("vite", "GHSA-2222-3333-4444", "high"))
    crit = npm_report(("vite", "GHSA-2222-3333-4444", "critical"))
    assert run(tmp_path, [("frontend", "tooling", "npm", 1, high)])[0] == 0
    assert run(tmp_path, [("frontend", "tooling", "npm", 1, crit)])[0] == 1


def test_thresholds_are_configurable(tmp_path):
    moderate = npm_report(("x", "GHSA-2222-3333-4444", "moderate"))
    src = [("frontend", "runtime", "npm", 1, moderate)]
    assert run(tmp_path, src, AUDIT_RUNTIME_FAIL_LEVEL="moderate")[0] == 1
    assert run(tmp_path, src, AUDIT_RUNTIME_FAIL_LEVEL="none")[0] == 0


def test_tooling_excludes_findings_already_in_runtime(tmp_path):
    rc, out = run(
        tmp_path,
        [
            ("frontend", "runtime", "npm", 1, HIGH_AXIOS),
            ("frontend", "tooling", "npm", 1, HIGH_AXIOS),
        ],
    )
    assert rc == 1
    assert out.count("GHSA-aaaa-bbbb-cccc") == 1


def test_osv_cvss_severity_and_unknown_default(tmp_path):
    high = osv_report(
        "jinja2", "2.10", ["PYSEC-2019-217", "GHSA-462w-v97r-4m45"], ["CVE-2019-10906"], "8.6"
    )
    rc, out = run(tmp_path, [("backend", "runtime", "osv", 1, high)])
    assert rc == 1 and "GHSA-462w-v97r-4m45" in out and "high" in out
    unknown = osv_report("foo", "1.0", ["PYSEC-2099-1"], [], "")
    assert run(tmp_path, [("backend", "runtime", "osv", 1, unknown)])[0] == 1  # unknown -> high
    assert (
        run(tmp_path, [("backend", "runtime", "osv", 1, unknown)], AUDIT_UNKNOWN_SEVERITY="low")[0]
        == 0
    )


# ------------------------------------------------------------- failures never look clean


@pytest.mark.parametrize(
    ("fmt", "rc", "data"),
    [
        ("npm", 1, NPM_ERROR),  # registry unreachable
        ("npm", 1, {"vulnerabilities": {}}),  # no metadata.vulnerabilities
        ("npm", 1, npm_report()),  # exit 1 ("vulnerable") but nothing to extract
        ("npm", 1, NPM_STRING_VIA_ONLY),  # only "because of X" entries, X missing
        ("npm", 0, NPM_TOTAL_WITHOUT_ADVISORIES),  # metadata total > 0, nothing extracted
        ("npm", 0, "npm ERR! not json"),
        ("npm", 7, npm_report()),  # unexpected exit code
        ("osv", 127, OSV_EMPTY),  # osv.dev unreachable: valid-looking empty JSON
        ("osv", 128, OSV_EMPTY),  # no packages found
        ("osv", 1, OSV_EMPTY),  # claims vulns but lists none
        ("osv", 0, {"oops": True}),
    ],
)
def test_scanner_failures_exit_2(tmp_path, fmt, rc, data):
    code, out = run(tmp_path, [("x", "runtime", fmt, rc, data)])
    assert code == 2
    assert "SCANNER FAILURE" in out and "NOT a clean result" in out
    assert "clean per policy" not in out


def test_failure_wins_over_violation(tmp_path):
    rc, _ = run(
        tmp_path,
        [
            ("frontend", "runtime", "npm", 1, HIGH_AXIOS),
            ("backend", "runtime", "osv", 127, OSV_EMPTY),
        ],
    )
    assert rc == 2


def test_missing_scanner_output_exits_2(tmp_path):
    src = ap.Source("backend", "runtime", "osv", str(tmp_path / "nope.json"), 0)
    assert (
        ap.evaluate([src], [], ap.policy_from_env({"AUDIT_TODAY": TODAY}), out=io.StringIO()) == 2
    )


# --------------------------------------------------------------------------- exceptions


def test_exception_suppresses_exact_match_only(tmp_path):
    src = [("frontend", "runtime", "npm", 1, HIGH_AXIOS)]
    rc, out = run(tmp_path, src, [exception()])
    assert rc == 0 and "EXCEPTED" in out
    # Wrong package, wrong scope or wrong id: no suppression.
    assert run(tmp_path, src, [exception(package="form-data")])[0] == 1
    assert run(tmp_path, src, [exception(scope="tooling")])[0] == 1
    assert run(tmp_path, src, [exception(id="GHSA-zzzz-zzzz-zzzz")])[0] == 1


def test_exception_must_match_severity(tmp_path):
    src = [("frontend", "runtime", "npm", 1, HIGH_AXIOS)]
    rc, out = run(tmp_path, src, [exception(severity="low")])
    assert rc == 1
    assert "[FAIL" in out and "EXCEPTED" not in out
    assert "is for severity 'low' but the finding is 'high'; not applied" in out
    assert run(tmp_path, src, [exception(severity="HIGH")])[0] == 0  # case-insensitive


def test_exception_matches_osv_alias(tmp_path):
    vuln = osv_report(
        "jinja2", "2.10", ["PYSEC-2019-217", "GHSA-462w-v97r-4m45"], ["CVE-2019-10906"], "8.6"
    )
    exc = exception(id="CVE-2019-10906", package="Jinja2")
    assert run(tmp_path, [("backend", "runtime", "osv", 1, vuln)], [exc])[0] == 0


def test_expired_exception_fails_even_if_unused(tmp_path):
    rc, out = run(
        tmp_path,
        [("frontend", "runtime", "npm", 0, npm_report())],
        [exception(expires="2026-11-04")],
    )
    assert rc == 1
    assert "EXPIRED on 2026-11-04" in out


def test_expired_exception_does_not_suppress(tmp_path):
    rc, out = run(
        tmp_path, [("frontend", "runtime", "npm", 1, HIGH_AXIOS)], [exception(expires="2026-10-01")]
    )
    assert rc == 1 and "[FAIL" in out


def test_exception_beyond_max_days_fails(tmp_path):
    rc, out = run(
        tmp_path,
        [("frontend", "runtime", "npm", 0, npm_report())],
        [exception(expires="2027-06-01")],
    )
    assert rc == 1 and "more than 90 days" in out


@pytest.mark.parametrize(
    "bad",
    [
        {"not": "a list"},
        [exception(owner="")],
        [exception(scope="prod")],
        [exception(expires="soon")],
    ],
)
def test_invalid_exceptions_file_exits_2(tmp_path, bad):
    path = write(tmp_path, "exc.json", bad)
    with pytest.raises(ap.AuditError):
        ap.load_exceptions(path)
    src = write(tmp_path, "npm.json", npm_report())
    code = ap.main(
        ["--source", f"frontend:runtime:npm:0:{src}", "--exceptions", path],
        env={"AUDIT_TODAY": TODAY},
    )
    assert code == 2


def test_invalid_threshold_exits_2(tmp_path):
    src = write(tmp_path, "npm.json", npm_report())
    exc = write(tmp_path, "exc.json", [])
    env = {"AUDIT_TODAY": TODAY, "AUDIT_RUNTIME_FAIL_LEVEL": "severe"}
    assert ap.main(["--source", f"frontend:runtime:npm:0:{src}", "--exceptions", exc], env=env) == 2


def test_repo_exceptions_file_is_valid():
    ap.load_exceptions(str(ROOT / "security" / "audit-exceptions.json"))


# --------------------------------------------------------------------------- shell wrapper


def _fake_bin(directory: Path, name: str, body: str) -> None:
    path = directory / name
    path.write_text("#!/usr/bin/env bash\n" + body)
    path.chmod(path.stat().st_mode | stat.S_IEXEC)


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash required")
@pytest.mark.parametrize(
    ("npm_json", "npm_rc", "osv_rc", "expected"),
    [
        (npm_report(), 0, 0, 0),
        (HIGH_AXIOS, 1, 0, 1),
        (NPM_ERROR, 1, 0, 2),
        (npm_report(), 0, 127, 2),
    ],
)
def test_shell_wrapper_exit_codes(tmp_path, npm_json, npm_rc, osv_rc, expected):
    bindir = tmp_path / "bin"
    bindir.mkdir()
    npm_file = write(tmp_path, "npm.json", npm_json)
    _fake_bin(bindir, "npm", f'cat "{npm_file}"; exit {npm_rc}\n')
    # uv export -o FILE: write a one-line requirements file.
    _fake_bin(
        bindir, "uv", 'while [[ $# -gt 0 ]]; do [[ $1 == -o ]] && echo "x==1" > "$2"; shift; done\n'
    )
    _fake_bin(bindir, "osv-scanner", f"echo '{json.dumps(OSV_EMPTY)}'; exit {osv_rc}\n")
    env = {
        **os.environ,
        "PATH": f"{bindir}{os.pathsep}{os.environ['PATH']}",
        "AUDIT_TODAY": TODAY,
        "AUDIT_EXCEPTIONS_FILE": write(tmp_path, "exc.json", []),
    }
    proc = subprocess.run(
        ["bash", str(ROOT / "scripts" / "audit-deps.sh")],
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == expected, proc.stdout + proc.stderr
    if expected == 2:
        assert "clean per policy" not in proc.stdout
