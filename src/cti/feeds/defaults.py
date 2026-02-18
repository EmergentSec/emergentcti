"""Default feed configurations seeded on startup.

Each entry matches the Feed model fields. File-type feeds use CSV parsing
with comment-char filtering for plain-text IOC lists.
"""

from cti.models.feed import FeedType

DEFAULT_FEEDS: list[dict] = [
    {
        "name": "AbuseIPDB",
        "description": (
            "Community-driven IP reputation database. Reports include abuse "
            "categories, report counts, and confidence scores."
        ),
        "feed_type": FeedType.api,
        "url": "https://api.abuseipdb.com/api/v2/blacklist?confidenceMinimum=90",
        "config": {
            "headers": {"Accept": "application/json"},
            "results_path": "data",
            "field_map": {
                "value": "ipAddress",
                "confidence_score": "abuseConfidenceScore",
                "last_seen": "lastReportedAt",
            },
            "default_type": "ip-addr",
        },
        "schedule_cron": "0 */6 * * *",
        "enabled": True,
        "default_ttl_days": 30,
        "requires_api_key_env": "ABUSEIPDB_API_KEY",
        "auth_config_template": {
            "auth_type": "api_key",
            "api_key_header": "Key",
        },
    },
    {
        "name": "Blocklist.de",
        "description": (
            "German-based honeypot and fail2ban aggregation project. Collects "
            "IPs flagged for brute-force attacks, scanning, and other abuse."
        ),
        "feed_type": FeedType.file,
        "url": "https://lists.blocklist.de/lists/all.txt",
        "config": {
            "format": "csv",
            "csv": {
                "has_header": False,
                "column_map": {"value": 0},
                "default_type": "ip-addr",
                "comment_char": "#",
            },
        },
        "schedule_cron": "0 */8 * * *",
        "enabled": True,
        "default_ttl_days": 14,
    },
    {
        "name": "Emerging Threats",
        "description": (
            "Proofpoint Emerging Threats ruleset for compromised IPs. Sourced "
            "from network sensors, honeypots, and malware analysis."
        ),
        "feed_type": FeedType.file,
        "url": "https://rules.emergingthreats.net/blockrules/compromised-ips.txt",
        "config": {
            "format": "csv",
            "csv": {
                "has_header": False,
                "column_map": {"value": 0},
                "default_type": "ip-addr",
                "comment_char": "#",
            },
        },
        "schedule_cron": "0 */4 * * *",
        "enabled": True,
        "default_ttl_days": 14,
    },
    {
        "name": "OpenPhish",
        "description": (
            "Community phishing URL feed. URLs are verified as active phishing "
            "pages with high confidence."
        ),
        "feed_type": FeedType.file,
        "url": "https://openphish.com/feed.txt",
        "config": {
            "format": "csv",
            "csv": {
                "has_header": False,
                "column_map": {"value": 0},
                "default_type": "url",
                "comment_char": "#",
            },
        },
        "schedule_cron": "0 */2 * * *",
        "enabled": True,
        "default_ttl_days": 7,
    },
    {
        "name": "Tor Exit Nodes",
        "description": (
            "Official Tor exit node IP list from the Tor Project. Low confidence "
            "because Tor usage is legitimate in many contexts."
        ),
        "feed_type": FeedType.file,
        "url": "https://check.torproject.org/torbulkexitlist",
        "config": {
            "format": "csv",
            "csv": {
                "has_header": False,
                "column_map": {"value": 0},
                "default_type": "ip-addr",
                "comment_char": "#",
            },
        },
        "schedule_cron": "0 */12 * * *",
        "enabled": True,
        "default_ttl_days": 7,
    },
    {
        "name": "URLhaus",
        "description": (
            "abuse.ch project tracking malware distribution URLs. Community-submitted "
            "URLs with moderate curation."
        ),
        "feed_type": FeedType.file,
        "url": "https://urlhaus.abuse.ch/downloads/text_recent/",
        "config": {
            "format": "csv",
            "csv": {
                "has_header": False,
                "column_map": {"value": 0},
                "default_type": "url",
                "comment_char": "#",
            },
        },
        "schedule_cron": "0 */3 * * *",
        "enabled": True,
        "default_ttl_days": 14,
    },
]
