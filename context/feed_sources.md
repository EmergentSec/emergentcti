# Feed Sources -- Configured Threat Intelligence Feeds

## Overview

EmergentCTI ships with 6 pre-configured threat intelligence feeds spanning different threat categories and data sources. Each feed uses one of the four connector types (api, taxii, file, scraper) and has its own confidence rating based on source reliability and data curation level.

---

## Feed Inventory

### 1. AbuseIPDB

| Property | Value |
|----------|-------|
| **Name** | AbuseIPDB |
| **Feed Type** | `api` |
| **Connector** | `APIFeedConnector` |
| **URL** | `https://api.abuseipdb.com/api/v2/blacklist` |
| **Schedule** | `0 */6 * * *` (every 6 hours) |
| **Default Confidence** | 90 |
| **Observable Types** | `ip-addr` |
| **Default Category** | varies (from report categories) |
| **Auth** | API key (Header: `Key`) |
| **Default TTL** | 30 days |

**Description:** Community-driven IP reputation database. Reports include abuse categories, report counts, and confidence scores. High confidence due to curated community reports with built-in scoring.

**Data quality notes:**
- Returns `abuseConfidenceScore` (0-100) per IP which can override feed default
- Categories include: SSH brute-force, web attacks, DDoS, spam, port scanning
- Free tier: 1000 reports/day, 5 checks/sec

---

### 2. Emerging Threats (Proofpoint ET)

| Property | Value |
|----------|-------|
| **Name** | Emerging Threats |
| **Feed Type** | `file` |
| **Connector** | `FileFeedConnector` |
| **URL** | `https://rules.emergingthreats.net/blockrules/compromised-ips.txt` |
| **Schedule** | `0 */4 * * *` (every 4 hours) |
| **Default Confidence** | 70 |
| **Observable Types** | `ip-addr` |
| **Default Category** | `malware` |
| **Auth** | None (public feed) |
| **Default TTL** | 14 days |

**Description:** Proofpoint's Emerging Threats ruleset for compromised IPs. Broadly sourced from network sensors, honeypots, and malware analysis. Moderate confidence due to wide coverage that may include false positives.

**Data quality notes:**
- Plain text format, one IP per line
- Updated frequently, but some IPs may be stale
- No individual scores per IP; uses feed default confidence

---

### 3. Blocklist.de

| Property | Value |
|----------|-------|
| **Name** | Blocklist.de |
| **Feed Type** | `file` |
| **Connector** | `FileFeedConnector` |
| **URL** | `https://lists.blocklist.de/lists/all.txt` |
| **Schedule** | `0 */8 * * *` (every 8 hours) |
| **Default Confidence** | 65 |
| **Observable Types** | `ip-addr` |
| **Default Category** | `scanner` |
| **Auth** | None (public feed) |
| **Default TTL** | 14 days |

**Description:** German-based honeypot and fail2ban aggregation project. Collects IPs flagged by participating servers for brute-force attacks, scanning, and other abuse. Lower confidence because it is fully automated with no manual curation.

**Data quality notes:**
- Plain text format, one IP per line
- High volume of IPs (100k+)
- Primarily brute-force and scanning activity
- Some legitimate scanners may appear (Shodan, Censys)

---

### 4. Tor Exit Nodes

| Property | Value |
|----------|-------|
| **Name** | Tor Exit Nodes |
| **Feed Type** | `file` |
| **Connector** | `FileFeedConnector` |
| **URL** | `https://check.torproject.org/torbulkexitlist` |
| **Schedule** | `0 */12 * * *` (every 12 hours) |
| **Default Confidence** | 30 |
| **Observable Types** | `ip-addr` |
| **Default Category** | `suspicious` |
| **Auth** | None (public feed) |
| **Default TTL** | 7 days |

**Description:** Official list of Tor exit node IP addresses from the Tor Project. Low confidence because Tor usage is legitimate in many contexts (privacy, censorship circumvention). These IPs are not inherently malicious but are useful for context.

**Data quality notes:**
- Plain text format, one IP per line
- Very accurate (official Tor Project source)
- Short TTL because exit nodes change frequently
- Should not be used alone for blocking decisions

---

### 5. OpenPhish

| Property | Value |
|----------|-------|
| **Name** | OpenPhish |
| **Feed Type** | `file` |
| **Connector** | `FileFeedConnector` |
| **URL** | `https://openphish.com/feed.txt` |
| **Schedule** | `0 */2 * * *` (every 2 hours) |
| **Default Confidence** | 80 |
| **Observable Types** | `url` |
| **Default Category** | `phishing` |
| **Auth** | None (community feed) |
| **Default TTL** | 7 days |

**Description:** Community phishing URL feed maintained by OpenPhish. URLs are verified as active phishing pages. High confidence due to verification process, though the free community feed is a subset of the premium feed.

**Data quality notes:**
- Plain text format, one URL per line
- Community feed is limited to ~500 URLs
- Premium feed has more URLs and faster updates
- Short TTL because phishing pages are taken down quickly

---

### 6. URLhaus (abuse.ch)

| Property | Value |
|----------|-------|
| **Name** | URLhaus |
| **Feed Type** | `file` |
| **Connector** | `FileFeedConnector` |
| **URL** | `https://urlhaus.abuse.ch/downloads/text_recent/` |
| **Schedule** | `0 */3 * * *` (every 3 hours) |
| **Default Confidence** | 75 |
| **Observable Types** | `url` |
| **Default Category** | `malware` |
| **Auth** | None (public feed) |
| **Default TTL** | 14 days |

**Description:** abuse.ch project tracking malware distribution URLs. Community-submitted URLs with moderate curation.

**Data quality notes:**
- Plain text format, one URL per line (comment lines start with `#`)
- URLs may be offline but still historically relevant
- Switched from API endpoint (`urlhaus-api.abuse.ch`) which returned 401

---

## Confidence Comparison

```
AbuseIPDB        ████████████████████████████████████████████████ 90
OpenPhish        ████████████████████████████████████████         80
URLhaus          ██████████████████████████████████████           75
Emerging Threats ████████████████████████████████████             70
Blocklist.de     █████████████████████████████████                65
Tor Exit Nodes   ███████████████                                  30
```

---

## Adding a New Feed

Refer to `goals/feed_ingestion.md` for the complete workflow to add and configure new feed sources.

---

## Related Files

- **Feed model:** `src/cti/models/feed.py`
- **Connectors:** `src/cti/feeds/api_connector.py`, `file_connector.py`, `taxii_connector.py`, `scraper_connector.py`
- **Confidence model:** `context/confidence_model.md`
- **Goal:** `goals/feed_ingestion.md`
