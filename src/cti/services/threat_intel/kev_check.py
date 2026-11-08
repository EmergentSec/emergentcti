#!/usr/bin/env python3
"""CISA KEV membership check for a single CVE id.

Fetches the CISA Known Exploited Vulnerabilities catalog (primary source) and
reports whether the given CVE is listed, with dateAdded / dueDate /
knownRansomwareCampaignUse. Rationale (threat-intel pipeline, verified 2026-07-17):
a cluster does not flip as a unit — check each CVE ID individually against the
catalog itself, never a press summary; a negative ("not in KEV") needs the same
primary check as a positive, and must never be conflated with "couldn't check".

Stdout: exactly one machine-readable status line.
Exit codes:
  0  in KEV
  1  NOT in KEV (catalog fetched and parsed successfully)
  2  ERROR — fetch/parse failed; membership UNKNOWN. Do not treat as "not in KEV".

Usage: kev_check.py CVE-YYYY-NNNN [--no-cache]
Catalog is cached at /tmp/cisa_kev_cache.json for 4h (KEV updates ~daily;
several CVEs get checked per run). --no-cache forces a fresh fetch.
No dependencies beyond the Python 3 stdlib.
"""
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

KEV_URL = (
    "https://www.cisa.gov/sites/default/files/feeds/"
    "known_exploited_vulnerabilities.json"
)
CACHE = Path("/tmp/cisa_kev_cache.json")
CACHE_TTL_SECONDS = 4 * 3600
FETCH_TIMEOUT = 45


def load_catalog(use_cache: bool):
    if (
        use_cache
        and CACHE.is_file()
        and time.time() - CACHE.stat().st_mtime < CACHE_TTL_SECONDS
    ):
        try:
            return json.loads(CACHE.read_text()), "cache"
        except (json.JSONDecodeError, OSError):
            pass  # stale/corrupt cache: fall through to fetch
    req = urllib.request.Request(KEV_URL, headers={"User-Agent": "emergent-cti-kev-check/1.0"})
    with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT) as resp:
        raw = resp.read()
    catalog = json.loads(raw)
    try:
        CACHE.write_bytes(raw)
    except OSError:
        pass  # cache write failure is non-fatal
    return catalog, "fetch"


def main() -> int:
    args = [a for a in sys.argv[1:] if a != "--no-cache"]
    use_cache = "--no-cache" not in sys.argv
    if len(args) != 1 or not re.fullmatch(r"CVE-\d{4}-\d{4,}", args[0], re.IGNORECASE):
        print("KEV_CHECK status=ERROR reason=usage expected=CVE-YYYY-NNNN [--no-cache]")
        return 2
    cve = args[0].upper()

    try:
        catalog, source = load_catalog(use_cache)
        vulns = catalog["vulnerabilities"]
        version = catalog.get("catalogVersion", "unknown")
    except Exception as exc:  # network, JSON, schema — membership is UNKNOWN
        print(
            f"KEV_CHECK cve={cve} status=ERROR in_kev=unknown "
            f"reason={type(exc).__name__} detail={str(exc)[:120]!r}"
        )
        return 2

    entry = next((v for v in vulns if v.get("cveID", "").upper() == cve), None)
    if entry is None:
        print(
            f"KEV_CHECK cve={cve} in_kev=no catalog_version={version} "
            f"catalog_count={len(vulns)} source={source}"
        )
        return 1

    ransomware = str(entry.get("knownRansomwareCampaignUse", "Unknown")).replace(" ", "_")
    print(
        f"KEV_CHECK cve={cve} in_kev=yes "
        f"date_added={entry.get('dateAdded', '?')} "
        f"due_date={entry.get('dueDate', '?')} "
        f"ransomware={ransomware} "
        f"catalog_version={version} source={source}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
