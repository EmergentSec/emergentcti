# Hard Prompt: Feed Source Evaluation

## Purpose

This template guides the evaluation of new threat intelligence feed sources before integration into the EmergentCTI platform. It provides a structured framework for assessing source reliability, data quality, integration complexity, and operational fit.

---

## Instructions

You are evaluating a candidate threat intelligence feed for integration into EmergentCTI. Analyze the feed against each criterion below and produce a structured assessment with a final recommendation (INTEGRATE / DEFER / REJECT).

### Evaluation Criteria

Score each criterion on a scale of 1-5:
- 5 = Excellent
- 4 = Good
- 3 = Acceptable
- 2 = Below average
- 1 = Poor

---

## Assessment Template

### Feed Identity

```
Feed Name:        [Name]
Provider:         [Organization or project]
URL:              [Feed endpoint or documentation URL]
Feed Type:        [api / taxii / file / scraper]
License:          [Open source / Community / Commercial / Government]
Cost:             [Free / Freemium / Paid ($X/month)]
```

### 1. Source Reliability (weight: 25%)

| Factor | Score (1-5) | Notes |
|--------|-------------|-------|
| Provider reputation | | Is the provider well-known in the security community? |
| Data provenance | | Is it clear where the data comes from? |
| Update consistency | | Does the feed update on a reliable schedule? |
| Historical accuracy | | Have past indicators been validated as accurate? |
| False positive rate | | How often does the feed report benign items? |

**Reliability Score:** [average] / 5

**Assessment:** [2-3 sentences on source reliability]

### 2. Data Quality (weight: 25%)

| Factor | Score (1-5) | Notes |
|--------|-------------|-------|
| Data freshness | | How quickly do new indicators appear? |
| Indicator context | | Does the feed provide categories, tags, or descriptions? |
| Structured format | | Is the data well-structured (JSON, STIX) or raw text? |
| Deduplication | | Does the feed handle its own deduplication? |
| Volume appropriateness | | Is the volume manageable (not flooding with noise)? |

**Quality Score:** [average] / 5

**Assessment:** [2-3 sentences on data quality]

### 3. Observable Types Produced (weight: 15%)

| Observable Type | Supported | Volume Estimate |
|-----------------|-----------|-----------------|
| ip-addr | Yes/No | |
| domain-name | Yes/No | |
| url | Yes/No | |
| file-hash | Yes/No | |
| email-addr | Yes/No | |
| command-line | Yes/No | |
| user-agent | Yes/No | |
| certificate | Yes/No | |
| asn | Yes/No | |
| cidr | Yes/No | |

**Type Coverage Score:** [count of supported types] / 10

**Assessment:** [Does this feed fill gaps in current coverage? Refer to context/feed_sources.md]

### 4. Confidence Rating (weight: 15%)

Based on the reliability and quality assessments, recommend a default confidence score:

| Rating | Confidence Range | Criteria |
|--------|-----------------|----------|
| Very High | 85-100 | Curated, verified, low false positive rate |
| High | 70-84 | Good curation, some unverified indicators |
| Moderate | 50-69 | Automated collection, moderate curation |
| Low | 30-49 | High volume, minimal curation, context-dependent |
| Very Low | 10-29 | Raw data, high false positive rate, informational only |

**Recommended default_confidence:** [0-100]

**Rationale:** [Why this confidence level?]

### 5. Integration Complexity (weight: 10%)

| Factor | Score (1-5) | Notes |
|--------|-------------|-------|
| Authentication | | None / API key / OAuth / Certificate |
| Data parsing | | Standard format or custom parser needed? |
| Rate limiting | | What are the API limits? |
| Error handling | | Does the API return clear error responses? |
| Documentation | | Is the API well-documented? |

**Complexity Score:** [average] / 5

**Integration approach:**
- Connector type: [api / taxii / file / scraper]
- Estimated implementation time: [hours]
- Custom parser needed: [Yes / No]
- Auth configuration: [Description]

### 6. Operational Fit (weight: 10%)

| Factor | Score (1-5) | Notes |
|--------|-------------|-------|
| Complements existing feeds | | Does it cover gaps or overlap heavily? |
| Update frequency alignment | | Does the schedule fit our Celery beat? |
| Resource impact | | Will it strain storage, network, or API limits? |
| Maintenance burden | | Will it need frequent attention? |

**Fit Score:** [average] / 5

---

## Final Recommendation

### Weighted Score

```
Source Reliability:      [X] / 5  * 0.25 = [weighted]
Data Quality:           [X] / 5  * 0.25 = [weighted]
Observable Coverage:    [X] / 10 * 0.15 = [weighted]
Confidence Suitability: [1-5]    * 0.15 = [weighted]
Integration Complexity: [X] / 5  * 0.10 = [weighted]
Operational Fit:        [X] / 5  * 0.10 = [weighted]
                                   ──────────────
Total:                             [sum] / 5.0
```

### Verdict

| Score Range | Recommendation |
|-------------|---------------|
| 4.0 - 5.0 | INTEGRATE -- Add to the platform |
| 3.0 - 3.9 | DEFER -- Revisit when gaps emerge or feed improves |
| 0.0 - 2.9 | REJECT -- Does not meet quality standards |

**Recommendation:** [INTEGRATE / DEFER / REJECT]

### Implementation Plan (if INTEGRATE)

```
1. Feed config:
   - name: [feed_name]
   - feed_type: [type]
   - url: [endpoint]
   - schedule_cron: [cron expression]
   - default_confidence: [score]
   - default_ttl_days: [days]
   - default_category: [category]

2. Connector: [Existing connector / New custom connector needed]

3. Testing: [How to validate ingestion works correctly]

4. Monitoring: [What to watch after deployment]
```

---

## Related Files

- **Current feeds:** `context/feed_sources.md`
- **Feed ingestion goal:** `goals/feed_ingestion.md`
- **Connector base:** `src/cti/feeds/base.py`
- **Observable types:** `context/observable_types.md`
- **Confidence model:** `context/confidence_model.md`
