"""Pre-configured feed definitions for EmergentCTI.

Each entry defines a threat intelligence feed that can be loaded into the
database on first startup.  Feeds that require an API key list the expected
environment variable name so the UI can prompt the user.
"""

from __future__ import annotations

from cti.models.feed import FeedType

DEFAULT_FEEDS: list[dict] = [
    # ------------------------------------------------------------------
    # 1. AbuseIPDB
    # ------------------------------------------------------------------
    {
        "name": "AbuseIPDB",
        "feed_type": FeedType.API,
        "url": "https://api.abuseipdb.com/api/v2/blacklist",
        "config": {
            "params": {"confidenceMinimum": 90},
            "headers": {"Accept": "application/json"},
            "results_path": "data",
            "field_map": {
                "value": "ipAddress",
                "native_confidence": "abuseConfidenceScore",
            },
            "default_type": "ip-addr",
        },
        "schedule_cron": "0 */6 * * *",
        "default_confidence": 85,
        "requires_api_key": "ABUSEIPDB_API_KEY",
        "auth_config_template": {
            "auth_type": "api_key",
            "api_key_header": "Key",
        },
    },
    # ------------------------------------------------------------------
    # 2. ThreatFox (abuse.ch)
    # ------------------------------------------------------------------
    {
        "name": "ThreatFox",
        "feed_type": FeedType.API,
        "url": "https://threatfox-api.abuse.ch/api/v1/",
        "config": {
            "method": "POST",
            "request_body": {"query": "get_iocs", "days": 1},
            "results_path": "data",
            "field_map": {
                "value": "ioc",
                "type": "ioc_type",
                "native_confidence": "confidence_level",
            },
            "type_map": {
                "ip:port": "ip-addr",
                "domain": "domain-name",
                "url": "url",
                "md5_hash": "file-hash",
                "sha256_hash": "file-hash",
            },
        },
        "schedule_cron": "0 */4 * * *",
        "default_confidence": 70,
        "requires_api_key": "THREATFOX_API_KEY",
        "auth_config_template": {
            "auth_type": "api_key",
            "api_key_header": "Auth-Key",
        },
    },
    # ------------------------------------------------------------------
    # 3. CINSscore (replaces GreyNoise – free, no auth)
    # ------------------------------------------------------------------
    {
        "name": "CINSscore",
        "feed_type": FeedType.FILE,
        "url": "https://cinsscore.com/list/ci-badguys.txt",
        "config": {
            "format": "text",
            "default_type": "ip-addr",
            "comment_char": "#",
        },
        "schedule_cron": "0 3 * * *",
        "default_confidence": 65,
    },
    # ------------------------------------------------------------------
    # 4. urlscan.io
    # ------------------------------------------------------------------
    {
        "name": "urlscan.io",
        "feed_type": FeedType.API,
        "url": "https://urlscan.io/api/v1/search/?q=task.tags:phishing&size=1000",
        "config": {
            "results_path": "results",
            "field_map": {
                "value": "page.url",
            },
            "default_type": "url",
        },
        "schedule_cron": "0 */6 * * *",
        "default_confidence": 65,
        "requires_api_key": "URLSCAN_API_KEY",
        "auth_config_template": {
            "auth_type": "bearer",
        },
    },
    # ------------------------------------------------------------------
    # 5. URLhaus (abuse.ch)
    # ------------------------------------------------------------------
    {
        "name": "URLhaus",
        "feed_type": FeedType.FILE,
        "url": "https://urlhaus.abuse.ch/downloads/text_recent/",
        "config": {
            "format": "text",
            "default_type": "url",
            "comment_char": "#",
        },
        "schedule_cron": "0 */3 * * *",
        "default_confidence": 75,
    },
    # ------------------------------------------------------------------
    # 6. Emerging Threats
    # ------------------------------------------------------------------
    {
        "name": "Emerging Threats",
        "feed_type": FeedType.FILE,
        "url": "https://rules.emergingthreats.net/blockrules/compromised-ips.txt",
        "config": {
            "format": "text",
            "default_type": "ip-addr",
            "comment_char": "#",
        },
        "schedule_cron": "0 */4 * * *",
        "default_confidence": 70,
    },
    # ------------------------------------------------------------------
    # 7. Tor Exit Nodes
    # ------------------------------------------------------------------
    {
        "name": "Tor Exit Nodes",
        "feed_type": FeedType.FILE,
        "url": "https://check.torproject.org/torbulkexitlist",
        "config": {
            "format": "text",
            "default_type": "ip-addr",
            "comment_char": "#",
        },
        "schedule_cron": "0 */12 * * *",
        "default_confidence": 30,
    },
    # ------------------------------------------------------------------
    # 8. Blocklist.de
    # ------------------------------------------------------------------
    {
        "name": "Blocklist.de",
        "feed_type": FeedType.FILE,
        "url": "https://lists.blocklist.de/lists/all.txt",
        "config": {
            "format": "text",
            "default_type": "ip-addr",
            "comment_char": "#",
        },
        "schedule_cron": "0 */8 * * *",
        "default_confidence": 60,
    },
    # ------------------------------------------------------------------
    # 9. OpenPhish
    # ------------------------------------------------------------------
    {
        "name": "OpenPhish",
        "feed_type": FeedType.FILE,
        "url": "https://openphish.com/feed.txt",
        "config": {
            "format": "text",
            "default_type": "url",
            "comment_char": "#",
        },
        "schedule_cron": "0 */2 * * *",
        "default_confidence": 80,
    },
    # ------------------------------------------------------------------
    # 10. Feodo Tracker
    # ------------------------------------------------------------------
    {
        "name": "Feodo Tracker",
        "feed_type": FeedType.FILE,
        "url": "https://feodotracker.abuse.ch/downloads/ipblocklist_recommended.txt",
        "config": {
            "format": "text",
            "default_type": "ip-addr",
            "comment_char": "#",
        },
        "schedule_cron": "0 */6 * * *",
        "default_confidence": 85,
    },
    # ------------------------------------------------------------------
    # 11. PhishTank
    # ------------------------------------------------------------------
    {
        "name": "PhishTank",
        "feed_type": FeedType.API,
        "url": "https://data.phishtank.com/data/{api_key}/online-valid.json",
        "config": {
            "field_map": {
                "value": "url",
            },
            "default_type": "url",
        },
        "schedule_cron": "0 */4 * * *",
        "default_confidence": 90,
        "requires_api_key": "PHISHTANK_API_KEY",
        "auth_config_template": {
            "auth_type": "url_template",
        },
    },
    # ------------------------------------------------------------------
    # 12. DShield
    # ------------------------------------------------------------------
    {
        "name": "DShield",
        "feed_type": FeedType.FILE,
        "url": "https://www.dshield.org/ipsascii.html?limit=10000",
        "config": {
            "format": "text",
            "default_type": "ip-addr",
            "comment_char": "#",
            "field_index": 0,
        },
        "schedule_cron": "0 */6 * * *",
        "default_confidence": 65,
    },
    # ------------------------------------------------------------------
    # 13. BinaryDefense
    # ------------------------------------------------------------------
    {
        "name": "BinaryDefense",
        "feed_type": FeedType.FILE,
        "url": "https://www.binarydefense.com/banlist.txt",
        "config": {
            "format": "text",
            "default_type": "ip-addr",
            "comment_char": "#",
        },
        "schedule_cron": "0 */8 * * *",
        "default_confidence": 70,
    },
]
