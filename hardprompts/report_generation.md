# Hard Prompt: Threat Intelligence Report Generation

## Purpose

This template guides the generation of structured threat intelligence reports from EmergentCTI platform data. Reports summarize observables, enrichment findings, MITRE ATT&CK mappings, and recommended actions for a specific investigation or time period.

---

## Instructions

You are generating a threat intelligence report for the EmergentCTI platform. Use the data provided (observables, enrichment results, correlation findings, ATT&CK mappings) to produce a structured report following the template below.

### Tone and Style

- Write for a technical audience (SOC analysts, incident responders, threat intel analysts)
- Use precise language; avoid speculation without evidence
- Quantify findings where possible (counts, percentages, confidence scores)
- Mark confidence levels explicitly: HIGH (70-100), MODERATE (40-69), LOW (0-39)
- Use TLP markings from the observable data

---

## Report Template

### Title Page

```
THREAT INTELLIGENCE REPORT
==========================

Title:      [Descriptive title based on primary threat]
Report ID:  [UUID or sequential ID]
Date:       [Generation date]
TLP:        [Highest TLP marking from included observables]
Period:     [Date range of observables analyzed]
Author:     EmergentCTI Platform (automated)
```

### 1. Executive Summary

Write 3-5 sentences summarizing:
- Total observables analyzed and their breakdown by type
- Key threats identified (highest confidence observables)
- Most active threat categories
- Recommended priority actions

```
During the reporting period [DATE_RANGE], the platform processed [N] observables
across [N] types. The primary threats identified include [THREAT_1] and [THREAT_2],
with [N] high-confidence indicators (score >= 70). Immediate attention is recommended
for [SPECIFIC_ACTION].
```

### 2. Key Findings

Present the top findings as numbered items:

```
1. [FINDING]: [Description with supporting data]
   - Confidence: [HIGH/MODERATE/LOW] ([score])
   - Observable count: [N]
   - Sources: [Feed names]
   - ATT&CK mapping: [Technique IDs if applicable]

2. [FINDING]: ...
```

### 3. Observable Analysis

#### 3.1 Summary Statistics

| Metric | Value |
|--------|-------|
| Total observables | [N] |
| New (this period) | [N] |
| Updated | [N] |
| By type | ip-addr: N, domain-name: N, url: N, file-hash: N, ... |
| By category | malware: N, phishing: N, c2: N, ... |
| Avg confidence | [N] |

#### 3.2 High-Confidence Indicators (score >= 70)

List the top 20 observables sorted by confidence score descending:

| Type | Value | Confidence | Category | Sources | First Seen | Last Seen |
|------|-------|------------|----------|---------|------------|-----------|
| [type] | [value] | [score] | [category] | [feeds] | [date] | [date] |

#### 3.3 Enrichment Results

For enriched observables, summarize provider findings:

```
Observable: [type]:[value] (confidence: [score])
  - VirusTotal: [N]/[total] engines detected as malicious
  - AbuseIPDB: abuse confidence [score]%, [N] reports, categories: [list]
  - Shodan: [N] open ports, [N] vulnerabilities ([CVE list])
  - GreyNoise: classification=[malicious/benign/unknown]
  - URLScan: verdict=[malicious/clean], score=[N]
```

### 4. Threat Actor Attribution

If observables correlate to known threat actors or campaigns:

```
Threat Actor: [Name]
  - Aliases: [List]
  - Motivation: [espionage/financial/hacktivism/unknown]
  - Associated observables: [N]
  - Associated campaigns: [List]
  - Confidence in attribution: [HIGH/MODERATE/LOW]
```

### 5. MITRE ATT&CK Mapping

Map observed activity to ATT&CK techniques:

| Tactic | Technique | ID | Observable Evidence | Confidence |
|--------|-----------|----|---------------------|------------|
| Initial Access | Phishing | T1566 | [phishing URLs] | HIGH |
| Command and Control | Application Layer Protocol | T1071 | [C2 domains] | MODERATE |
| ... | ... | ... | ... | ... |

### 6. Correlations

Describe any correlation rule matches:

```
Correlation: [Rule name]
  - Description: [What the rule detects]
  - Matched observables: [List]
  - Significance: [Why this matters]
```

### 7. Recommendations

Provide actionable recommendations:

```
IMMEDIATE (within 24 hours):
  1. Block [specific indicators] at network perimeter
  2. Investigate [internal hosts] that communicated with [C2 domains]

SHORT-TERM (within 1 week):
  3. Update detection rules for [ATT&CK techniques]
  4. Enrich [low-confidence observables] with additional providers

LONG-TERM (within 1 month):
  5. Review [feed source] configuration for false positive rate
  6. Implement [specific detection capability]
```

### 8. Appendix

- Full observable list (for import into other tools)
- Raw enrichment data
- Feed run statistics for the period
- Methodology notes

---

## Usage

This template is used by:
- The report generation API endpoint
- Scheduled automated reports
- Manual analyst-triggered report generation

Feed the observable data and enrichment results into this template structure. The LLM fills in the analysis, interpretation, and recommendations based on the data.

---

## Related Files

- **Export service:** `src/cti/services/export_service.py`
- **Dashboard service:** `src/cti/services/dashboard_service.py`
- **ATT&CK service:** `src/cti/services/attack_service.py`
- **Context:** `context/observable_types.md`, `context/confidence_model.md`
