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
    # 2. AlienVault OTX
    # ------------------------------------------------------------------
    {
        "name": "AlienVault OTX",
        "feed_type": FeedType.API,
        "url": "https://otx.alienvault.com/api/v1/indicators/export",
        "config": {
            "results_path": "results",
            "field_map": {
                "value": "indicator",
                "type": "type",
            },
            "type_map": {
                "IPv4": "ip-addr",
                "domain": "domain-name",
                "URL": "url",
                "FileHash-MD5": "file-hash",
                "FileHash-SHA256": "file-hash",
                "email": "email-addr",
            },
        },
        "schedule_cron": "0 2 * * *",
        "default_confidence": 60,
        "requires_api_key": "OTX_API_KEY",
        "auth_config_template": {
            "auth_type": "api_key",
            "api_key_header": "X-OTX-API-KEY",
        },
    },
    # ------------------------------------------------------------------
    # 3. ThreatFox (abuse.ch)
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
    },
    # ------------------------------------------------------------------
    # 4. GreyNoise
    # ------------------------------------------------------------------
    {
        "name": "GreyNoise",
        "feed_type": FeedType.API,
        "url": "https://api.greynoise.io/v3/community/",
        "config": {
            "results_path": "data",
            "field_map": {
                "value": "ip",
                "native_confidence": "score",
            },
            "default_type": "ip-addr",
        },
        "schedule_cron": "0 3 * * *",
        "default_confidence": 65,
        "requires_api_key": "GREYNOISE_API_KEY",
        "auth_config_template": {
            "auth_type": "api_key",
            "api_key_header": "key",
        },
    },
    # ------------------------------------------------------------------
    # 5. urlscan.io
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
    # 6. URLhaus (abuse.ch)
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
    # 7. Emerging Threats
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
    # 8. Tor Exit Nodes
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
    # 9. Blocklist.de
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
    # 10. OpenPhish
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
    # 11. Feodo Tracker
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
    # 12. PhishTank
    # ------------------------------------------------------------------
    {
        "name": "PhishTank",
        "feed_type": FeedType.API,
        "url": "https://data.phishtank.com/data/online-valid.json",
        "config": {
            "field_map": {
                "value": "url",
            },
            "default_type": "url",
        },
        "schedule_cron": "0 */4 * * *",
        "default_confidence": 90,
    },
]
