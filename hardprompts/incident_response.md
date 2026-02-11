# Hard Prompt: Incident Response Workflow

## Purpose

This template guides incident response activities using EmergentCTI platform data. It structures the process from initial triage through observable extraction, enrichment, correlation, ATT&CK mapping, and containment recommendations.

---

## Instructions

You are assisting with an incident response investigation using the EmergentCTI platform. Follow the phases below in order. At each phase, use the platform's API and data to support the investigation. Document findings in the structured format provided.

### Investigation Principles

- Preserve evidence before taking containment actions
- Document every step with timestamps
- Correlate across multiple data sources before drawing conclusions
- Use confidence scores to prioritize investigation effort
- Follow the principle of least privilege when recommending access changes

---

## Phase 1: Initial Triage

### Incident Classification

```
Incident ID:      [Auto-generated or manual]
Reported by:      [Source: alert, user report, external notification]
Report time:      [ISO 8601 timestamp]
Severity:         [Critical / High / Medium / Low]
Category:         [malware / phishing / data_exfil / unauthorized_access / ransomware / other]
Status:           [New / Investigating / Contained / Resolved]
Assigned to:      [Analyst name]
```

### Initial Assessment Questions

Answer these within the first 15 minutes:

```
1. What triggered this incident?
   [ ] Platform alert (rule: _______)
   [ ] External notification (source: _______)
   [ ] User report
   [ ] Automated detection (tool: _______)

2. What is the scope?
   - Affected systems: [list]
   - Affected users: [list]
   - Affected data: [classification]

3. Is the threat active?
   [ ] Yes -- proceed to containment immediately
   [ ] No -- proceed with investigation
   [ ] Unknown -- treat as active until confirmed otherwise

4. What is the business impact?
   - [Describe operational impact]
```

---

## Phase 2: Observable Extraction

### Identify Observables

Extract all relevant indicators from available evidence. Use the EmergentCTI API to check if any are already known:

```bash
# Search for an IP address
curl "http://localhost:8080/api/v1/search?q=192.168.1.100" \
  -H "Authorization: Bearer $TOKEN"

# Look up a specific observable
curl "http://localhost:8080/api/v1/observables?type=ip-addr&value=192.168.1.100" \
  -H "Authorization: Bearer $TOKEN"
```

### Observable Collection Table

| # | Type | Value | Found in CTI? | Confidence | Source |
|---|------|-------|---------------|------------|--------|
| 1 | ip-addr | [IP] | Yes/No | [score or N/A] | [where extracted from] |
| 2 | domain-name | [domain] | Yes/No | [score or N/A] | [DNS logs, etc.] |
| 3 | file-hash | [hash] | Yes/No | [score or N/A] | [endpoint detection] |
| 4 | url | [URL] | Yes/No | [score or N/A] | [proxy logs, email] |

### Import New Observables

For indicators not already in the platform, bulk import them:

```bash
curl -X POST http://localhost:8080/api/v1/observables/bulk \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "observables": [
      {"type": "ip-addr", "value": "1.2.3.4", "confidence_score": 80, "category": "c2"},
      {"type": "domain-name", "value": "evil.example.com", "confidence_score": 85, "category": "c2"}
    ]
  }'
```

---

## Phase 3: Enrichment

### Enrich All Extracted Observables

Trigger enrichment for each observable to gather external intelligence:

```bash
# Enrich a specific observable with all available providers
curl -X POST http://localhost:8080/api/v1/enrichment/enrich/{observable_id} \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"providers": ["virustotal", "abuseipdb", "shodan", "greynoise", "urlscan"]}'
```

### Enrichment Findings Table

| Observable | Provider | Key Finding | Confidence Impact |
|-----------|----------|-------------|-------------------|
| [type:value] | VirusTotal | [N]/[total] engines flagged | [old] -> [new] |
| [type:value] | AbuseIPDB | abuse score [N]%, [N] reports | [old] -> [new] |
| [type:value] | Shodan | [N] open ports, [CVEs] | [old] -> [new] |
| [type:value] | GreyNoise | classification: [result] | [old] -> [new] |
| [type:value] | URLScan | verdict: [result] | [old] -> [new] |

### Enrichment Analysis

For each enriched observable, document:

```
Observable: [type]:[value]
  Pre-enrichment confidence: [score]
  Post-enrichment confidence: [score]
  Key findings:
    - [Finding 1]
    - [Finding 2]
  Assessment: [Confirmed malicious / Likely malicious / Inconclusive / Likely benign]
```

---

## Phase 4: Correlation

### Platform Correlations

Check for correlation rule matches and related observables:

```bash
# Check correlations for an observable
curl "http://localhost:8080/api/v1/correlations/matches?observable_id={id}" \
  -H "Authorization: Bearer $TOKEN"

# Find related observables (shared infrastructure, campaigns)
curl "http://localhost:8080/api/v1/relationships?observable_id={id}" \
  -H "Authorization: Bearer $TOKEN"
```

### Correlation Findings

```
Correlation 1: [Rule name]
  - Matching observables: [list]
  - Significance: [What this pattern indicates]
  - Related campaigns: [if any]
  - Related threat actors: [if any]

Correlation 2: ...
```

### Infrastructure Mapping

Document the relationship between observables:

```
C2 Infrastructure:
  [IP] ──resolves──> [domain]
  [domain] ──hosts──> [URL (malware download)]
  [URL] ──delivers──> [file-hash (payload)]
  [file-hash] ──contacts──> [IP (secondary C2)]
```

---

## Phase 5: ATT&CK Mapping

### Map Observed Activity to MITRE ATT&CK

Based on the evidence and enrichment results, map the attacker's activity:

```bash
# Look up ATT&CK techniques
curl "http://localhost:8080/api/v1/attack/techniques?search=phishing" \
  -H "Authorization: Bearer $TOKEN"
```

### ATT&CK Matrix Coverage

| Tactic | Technique | ID | Evidence | Confidence |
|--------|-----------|----|----------|------------|
| Initial Access | [Technique] | T[xxxx] | [Observable or log evidence] | HIGH/MED/LOW |
| Execution | [Technique] | T[xxxx] | [Evidence] | |
| Persistence | [Technique] | T[xxxx] | [Evidence] | |
| Privilege Escalation | [Technique] | T[xxxx] | [Evidence] | |
| Defense Evasion | [Technique] | T[xxxx] | [Evidence] | |
| Credential Access | [Technique] | T[xxxx] | [Evidence] | |
| Discovery | [Technique] | T[xxxx] | [Evidence] | |
| Lateral Movement | [Technique] | T[xxxx] | [Evidence] | |
| Collection | [Technique] | T[xxxx] | [Evidence] | |
| Command and Control | [Technique] | T[xxxx] | [Evidence] | |
| Exfiltration | [Technique] | T[xxxx] | [Evidence] | |
| Impact | [Technique] | T[xxxx] | [Evidence] | |

### Kill Chain Position

Based on the ATT&CK mapping, determine where in the attack lifecycle the adversary currently is:

```
[ ] Reconnaissance
[ ] Weaponization
[X] Delivery           <-- e.g., phishing email detected
[X] Exploitation       <-- e.g., malware executed
[ ] Installation
[X] Command & Control  <-- e.g., C2 beacon detected
[ ] Actions on Objectives
```

---

## Phase 6: Containment Recommendations

### Immediate Actions (within 1 hour)

```
BLOCK:
  [ ] Block IP [X.X.X.X] at firewall/IDS
  [ ] Block domain [evil.example.com] at DNS resolver
  [ ] Block URL [https://evil.example.com/payload] at proxy
  [ ] Block file hash [SHA256] at endpoint protection

ISOLATE:
  [ ] Isolate affected hosts from network
  [ ] Disable compromised user accounts
  [ ] Revoke compromised API keys/tokens

PRESERVE:
  [ ] Capture memory dump from affected hosts
  [ ] Preserve relevant log files
  [ ] Screenshot active sessions
```

### Short-Term Actions (within 24 hours)

```
INVESTIGATE:
  [ ] Perform forensic analysis on affected endpoints
  [ ] Review authentication logs for lateral movement
  [ ] Check for data exfiltration in proxy/DLP logs
  [ ] Scan for additional indicators across the environment

DETECT:
  [ ] Deploy detection rules for identified ATT&CK techniques
  [ ] Add observables to watchlists
  [ ] Configure alerts for related infrastructure
```

### Long-Term Actions (within 1 week)

```
REMEDIATE:
  [ ] Patch exploited vulnerabilities
  [ ] Reset credentials for affected accounts
  [ ] Review and harden access controls
  [ ] Update security policies based on lessons learned

RECOVER:
  [ ] Restore affected systems from clean backups
  [ ] Verify system integrity post-restoration
  [ ] Monitor for re-compromise indicators
```

---

## Phase 7: Documentation

### Incident Timeline

```
[TIMESTAMP] - [Event description]
[TIMESTAMP] - [Event description]
[TIMESTAMP] - [Event description]
...
```

### Lessons Learned

```
1. What worked well?
2. What could be improved?
3. Were there detection gaps?
4. Are there new indicators to add to feeds?
5. Should any platform rules be updated?
```

---

## Related Files

- **Report generation:** `hardprompts/report_generation.md`
- **ATT&CK service:** `src/cti/services/attack_service.py`
- **Alert service:** `src/cti/services/alert_service.py`
- **Correlation service:** `src/cti/services/correlation_service.py`
- **Observable types:** `context/observable_types.md`
- **Enrichment goal:** `goals/enrichment.md`
