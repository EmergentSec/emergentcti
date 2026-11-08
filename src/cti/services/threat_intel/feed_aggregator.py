#!/usr/bin/env python3
"""
Security Feed Aggregator
Monitors threat intel feeds, CVEs, and vendor advisories
"""

import hashlib
import json
import logging
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import feedparser
import httpx


class FeedAggregatorError(Exception):
    """Configuration or I/O failure in the feed aggregator."""


class FeedAggregator:
    def __init__(self, config_path: str = "config.json"):
        """Initialize the feed aggregator with configuration"""
        self.config = self._load_config(config_path)
        self.setup_logging()
        self.state_file = Path(self.config.get("state_file", "feed_state.json"))
        self.state = self._load_state()

    def _load_config(self, config_path: str) -> dict[str, Any]:
        """Load configuration from JSON file; env ``NVD_API_KEY`` overrides empty keys."""
        try:
            with open(config_path) as f:
                config = json.load(f)
        except FileNotFoundError as exc:
            raise FeedAggregatorError(f"Config file not found: {config_path}") from exc
        except json.JSONDecodeError as exc:
            raise FeedAggregatorError(f"Invalid JSON in config file: {exc}") from exc
        nvd = config.setdefault("nvd", {})
        if isinstance(nvd, dict) and not nvd.get("api_key"):
            env_key = os.environ.get("NVD_API_KEY", "").strip()
            if env_key:
                nvd["api_key"] = env_key
        return config
    
    def setup_logging(self):
        """Configure logging"""
        log_file = self.config.get("log_file", "feed_aggregator.log")
        log_level = self.config.get("log_level", "INFO")
        
        logging.basicConfig(
            level=getattr(logging, log_level),
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def _load_state(self) -> dict[str, Any]:
        """Load previous state to track seen items"""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                self.logger.warning("Corrupted state file, starting fresh")
                return {"seen_items": {}, "last_run": None}
        return {"seen_items": {}, "last_run": None}
    
    def _save_state(self):
        """Save current state"""
        self.state["last_run"] = datetime.now().isoformat()
        with open(self.state_file, 'w') as f:
            json.dump(self.state, f, indent=2)
    
    def _generate_item_id(self, item: dict[str, Any]) -> str:
        """Generate unique ID for an item"""
        content = f"{item.get('title', '')}{item.get('link', '')}{item.get('published', '')}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def _is_new_item(self, item_id: str) -> bool:
        """Check if item has been seen before"""
        return item_id not in self.state["seen_items"]
    
    def _mark_seen(self, item_id: str):
        """Mark item as seen"""
        self.state["seen_items"][item_id] = datetime.now().isoformat()
    
    def _matches_filters(self, item: dict[str, Any]) -> bool:
        """Check if item matches configured filters"""
        filters = self.config.get("filters", {})
        
        # Keyword filter
        keywords = filters.get("keywords", [])
        if keywords:
            text = f"{item.get('title', '')} {item.get('description', '')}".lower()
            if not any(kw.lower() in text for kw in keywords):
                return False
        
        # Severity filter (for CVEs)
        severity_filter = filters.get("severity", [])
        if severity_filter and "severity" in item:
            if item["severity"].lower() not in [s.lower() for s in severity_filter]:
                return False
        
        # Product filter
        products = filters.get("products", [])
        if products:
            text = f"{item.get('title', '')} {item.get('description', '')}".lower()
            if not any(prod.lower() in text for prod in products):
                return False
        
        return True
    
    def fetch_rss_feeds(self) -> list[dict[str, Any]]:
        """Fetch and parse RSS/Atom feeds"""
        items = []
        feeds = self.config.get("rss_feeds", [])
        
        for feed_config in feeds:
            url = feed_config["url"]
            source = feed_config.get("name", url)
            
            try:
                self.logger.info(f"Fetching feed: {source}")
                feed = feedparser.parse(url)
                
                for entry in feed.entries:
                    item = {
                        "source": source,
                        "type": "feed",
                        "title": entry.get("title", ""),
                        "link": entry.get("link", ""),
                        "description": entry.get("summary", ""),
                        "published": entry.get("published", entry.get("updated", "")),
                        "raw": entry
                    }
                    
                    item_id = self._generate_item_id(item)
                    
                    if self._is_new_item(item_id) and self._matches_filters(item):
                        items.append(item)
                        self._mark_seen(item_id)
                
                self.logger.info(f"Found {len(items)} new items from {source}")
                
            except Exception as e:
                self.logger.error(f"Error fetching feed {source}: {e}")
        
        return items
    
    def fetch_nvd_cves(self) -> list[dict[str, Any]]:
        """Fetch recent CVEs from NVD API"""
        items = []
        nvd_config = self.config.get("nvd", {})
        
        if not nvd_config.get("enabled", False):
            return items
        
        api_key = nvd_config.get("api_key")
        days_back = nvd_config.get("days_back", 1)
        
        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        
        url = "https://services.nvd.nist.gov/rest/json/cves/2.0"
        params = {
            "pubStartDate": start_date.strftime("%Y-%m-%dT00:00:00.000"),
            "pubEndDate": end_date.strftime("%Y-%m-%dT23:59:59.999")
        }
        
        headers = {}
        if api_key:
            headers["apiKey"] = api_key
        
        try:
            self.logger.info("Fetching CVEs from NVD")
            with httpx.Client(timeout=30.0) as client:
                response = client.get(url, params=params, headers=headers)
                response.raise_for_status()
                data = response.json()
            vulnerabilities = data.get("vulnerabilities", [])
            
            for vuln in vulnerabilities:
                cve = vuln.get("cve", {})
                cve_id = cve.get("id", "")
                
                # Extract severity
                metrics = cve.get("metrics", {})
                severity = "UNKNOWN"
                cvss_score = None
                
                if "cvssMetricV31" in metrics:
                    cvss_data = metrics["cvssMetricV31"][0]["cvssData"]
                    severity = cvss_data.get("baseSeverity", "UNKNOWN")
                    cvss_score = cvss_data.get("baseScore")
                elif "cvssMetricV2" in metrics:
                    cvss_data = metrics["cvssMetricV2"][0]["cvssData"]
                    cvss_score = cvss_data.get("baseScore")
                    # Map CVSS v2 score to severity
                    if cvss_score >= 7.0:
                        severity = "HIGH"
                    elif cvss_score >= 4.0:
                        severity = "MEDIUM"
                    else:
                        severity = "LOW"
                
                descriptions = cve.get("descriptions", [])
                description = next((d["value"] for d in descriptions if d["lang"] == "en"), "")
                
                item = {
                    "source": "NVD",
                    "type": "cve",
                    "cve_id": cve_id,
                    "title": f"{cve_id}: {description[:100]}...",
                    "link": f"https://nvd.nist.gov/vuln/detail/{cve_id}",
                    "description": description,
                    "severity": severity,
                    "cvss_score": cvss_score,
                    "published": cve.get("published", ""),
                    "raw": cve
                }
                
                item_id = self._generate_item_id(item)
                
                if self._is_new_item(item_id) and self._matches_filters(item):
                    items.append(item)
                    self._mark_seen(item_id)
            
            self.logger.info(f"Found {len(items)} new CVEs from NVD")
            
            # Respect rate limits
            time.sleep(6 if not api_key else 0.6)
            
        except Exception as e:
            self.logger.error(f"Error fetching NVD CVEs: {e}")
        
        return items
    
    def fetch_vendor_advisories(self) -> list[dict[str, Any]]:
        """Fetch vendor security advisories"""
        items = []
        vendors = self.config.get("vendors", [])
        
        for vendor_config in vendors:
            vendor_name = vendor_config["name"]
            if not vendor_config.get("enabled", True):
                self.logger.info(f"Skipping disabled vendor: {vendor_name}")
                continue
            
            if vendor_name.lower() == "microsoft":
                items.extend(self._fetch_microsoft_advisories(vendor_config))
            elif vendor_name.lower() == "cisco":
                items.extend(self._fetch_cisco_advisories(vendor_config))
            # Add more vendors as needed
        
        return items
    
    def _fetch_microsoft_advisories(self, config: dict[str, Any]) -> list[dict[str, Any]]:
        """Fetch Microsoft security advisories"""
        items = []
        
        # Microsoft Security Update Guide RSS
        url = "https://api.msrc.microsoft.com/update-guide/rss"
        
        try:
            self.logger.info("Fetching Microsoft advisories")
            feed = feedparser.parse(url)
            
            for entry in feed.entries:
                # Extract CVE number from GUID or title
                cve_number = entry.get("id", "")
                if not cve_number and "CVE-" in entry.get("title", ""):
                    # Extract CVE from title
                    title_parts = entry.get("title", "").split()
                    for part in title_parts:
                        if part.startswith("CVE-"):
                            cve_number = part
                            break
                
                item = {
                    "source": "Microsoft",
                    "type": "advisory",
                    "title": entry.get("title", ""),
                    "link": entry.get("link", ""),
                    "description": entry.get("summary", ""),
                    "published": entry.get("published", ""),
                    "raw": entry
                }
                
                # Fetch detailed severity information from MSRC API
                if cve_number and cve_number.startswith("CVE-"):
                    severity_data = self._fetch_microsoft_cve_details(cve_number)
                    if severity_data:
                        item.update(severity_data)
                
                item_id = self._generate_item_id(item)
                
                if self._is_new_item(item_id) and self._matches_filters(item):
                    items.append(item)
                    self._mark_seen(item_id)
            
            self.logger.info(f"Found {len(items)} new Microsoft advisories")
            
        except Exception as e:
            self.logger.error(f"Error fetching Microsoft advisories: {e}")
        
        return items
    
    def _fetch_microsoft_cve_details(self, cve_number: str) -> dict[str, Any] | None:
        """Fetch detailed CVE information from Microsoft MSRC API"""
        try:
            url = f"https://api.msrc.microsoft.com/sug/v2.0/en-US/vulnerability/{cve_number}"
            with httpx.Client(timeout=10.0) as client:
                response = client.get(url)
            if response.status_code == 200:
                data = response.json()
                
                severity = data.get("severity", "UNKNOWN")
                impact = data.get("impact", "")
                base_score = data.get("baseScore")
                temporal_score = data.get("temporalScore")
                
                result = {
                    "severity": severity.upper() if severity else "UNKNOWN",
                    "impact": impact
                }
                
                # Add CVSS scores if available
                if base_score:
                    try:
                        result["cvss_score"] = float(base_score)
                    except (ValueError, TypeError):
                        pass
                
                if temporal_score:
                    try:
                        result["cvss_temporal_score"] = float(temporal_score)
                    except (ValueError, TypeError):
                        pass
                
                # Map Microsoft severity to standard severity levels
                severity_mapping = {
                    "CRITICAL": "CRITICAL",
                    "IMPORTANT": "HIGH",
                    "MODERATE": "MEDIUM",
                    "LOW": "LOW"
                }
                
                if result["severity"] in severity_mapping:
                    result["severity"] = severity_mapping[result["severity"]]
                
                return result
            
            elif response.status_code == 404:
                # CVE not found in Microsoft database, might be third-party
                self.logger.debug(f"CVE {cve_number} not found in MSRC database")
                return None
            else:
                self.logger.warning(f"Failed to fetch details for {cve_number}: HTTP {response.status_code}")
                return None
                
        except Exception as e:
            self.logger.debug(f"Error fetching details for {cve_number}: {e}")
            return None
    
    def _fetch_cisco_advisories(self, config: dict[str, Any]) -> list[dict[str, Any]]:
        """Fetch Cisco security advisories"""
        items = []
        
        # Cisco Security Advisories RSS
        url = "https://sec.cloudapps.cisco.com/security/center/events.x?mode=rssfeed"
        
        try:
            self.logger.info("Fetching Cisco advisories")
            feed = feedparser.parse(url)
            
            for entry in feed.entries:
                item = {
                    "source": "Cisco",
                    "type": "advisory",
                    "title": entry.get("title", ""),
                    "link": entry.get("link", ""),
                    "description": entry.get("summary", ""),
                    "published": entry.get("published", ""),
                    "raw": entry
                }
                
                item_id = self._generate_item_id(item)
                
                if self._is_new_item(item_id) and self._matches_filters(item):
                    items.append(item)
                    self._mark_seen(item_id)
            
            self.logger.info(f"Found {len(items)} new Cisco advisories")
            
        except Exception as e:
            self.logger.error(f"Error fetching Cisco advisories: {e}")
        
        return items
    
    def aggregate(self) -> dict[str, Any]:
        """Aggregate all sources and generate report"""
        self.logger.info("Starting feed aggregation")
        
        all_items = []
        
        # Fetch from all sources
        all_items.extend(self.fetch_rss_feeds())
        all_items.extend(self.fetch_nvd_cves())
        all_items.extend(self.fetch_vendor_advisories())
        
        # Sort by severity and date
        severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "UNKNOWN": 4}
        all_items.sort(
            key=lambda x: (
                severity_order.get(x.get("severity", "UNKNOWN"), 4),
                x.get("published", "")
            ),
            reverse=True
        )
        
        # Generate report
        report = {
            "timestamp": datetime.now().isoformat(),
            "total_items": len(all_items),
            "summary": self._generate_summary(all_items),
            "items": all_items
        }
        
        # Save state
        self._save_state()
        
        self.logger.info(f"Aggregation complete: {len(all_items)} total items")
        
        return report
    
    def _generate_summary(self, items: list[dict[str, Any]]) -> dict[str, Any]:
        """Generate summary statistics"""
        summary = {
            "by_source": {},
            "by_type": {},
            "by_severity": {}
        }
        
        for item in items:
            # By source
            source = item.get("source", "Unknown")
            summary["by_source"][source] = summary["by_source"].get(source, 0) + 1
            
            # By type
            item_type = item.get("type", "unknown")
            summary["by_type"][item_type] = summary["by_type"].get(item_type, 0) + 1
            
            # By severity
            severity = item.get("severity", "N/A")
            summary["by_severity"][severity] = summary["by_severity"].get(severity, 0) + 1
        
        return summary
    
    def save_json_report(self, report: dict[str, Any], output_file: str = None):
        """Save report as JSON"""
        if output_file is None:
            output_file = f"feed_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        with open(output_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        self.logger.info(f"JSON report saved to: {output_file}")
    
    def generate_human_readable(self, report: dict[str, Any]) -> str:
        """Generate human-readable summary"""
        lines = []
        lines.append("=" * 80)
        lines.append("SECURITY FEED AGGREGATOR REPORT")
        lines.append("=" * 80)
        lines.append(f"Generated: {report['timestamp']}")
        lines.append(f"Total Items: {report['total_items']}")
        lines.append("")
        
        # Summary section
        lines.append("SUMMARY")
        lines.append("-" * 80)
        
        summary = report["summary"]
        
        lines.append("\nBy Source:")
        for source, count in sorted(summary["by_source"].items(), key=lambda x: x[1], reverse=True):
            lines.append(f"  {source}: {count}")
        
        lines.append("\nBy Type:")
        for item_type, count in sorted(summary["by_type"].items(), key=lambda x: x[1], reverse=True):
            lines.append(f"  {item_type}: {count}")
        
        lines.append("\nBy Severity:")
        for severity, count in sorted(summary["by_severity"].items(), key=lambda x: x[1], reverse=True):
            lines.append(f"  {severity}: {count}")
        
        # Detailed items
        lines.append("\n" + "=" * 80)
        lines.append("DETAILED FINDINGS")
        lines.append("=" * 80)
        
        for idx, item in enumerate(report["items"], 1):
            lines.append(f"\n[{idx}] {item['title']}")
            lines.append(f"    Source: {item['source']} | Type: {item['type']}")
            if "severity" in item:
                sev_line = f"    Severity: {item['severity']}"
                if "cvss_score" in item and item["cvss_score"]:
                    sev_line += f" (CVSS: {item['cvss_score']})"
                lines.append(sev_line)
            lines.append(f"    Link: {item['link']}")
            if item.get("published"):
                lines.append(f"    Published: {item['published']}")
            lines.append(f"    Description: {item['description'][:200]}...")
        
        lines.append("\n" + "=" * 80)
        lines.append("END OF REPORT")
        lines.append("=" * 80)
        
        return "\n".join(lines)
    
    def save_human_readable(self, report: dict[str, Any], output_file: str = None):
        """Save human-readable report"""
        if output_file is None:
            output_file = f"feed_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        
        content = self.generate_human_readable(report)
        
        with open(output_file, 'w') as f:
            f.write(content)
        
        self.logger.info(f"Human-readable report saved to: {output_file}")
        
        return content


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Security Feed Aggregator")
    parser.add_argument(
        "--config",
        default="config.json",
        help="Path to configuration file (default: config.json)"
    )
    parser.add_argument(
        "--json-output",
        help="Path to JSON output file"
    )
    parser.add_argument(
        "--text-output",
        help="Path to text output file"
    )
    parser.add_argument(
        "--print",
        action="store_true",
        help="Print human-readable report to stdout"
    )
    
    args = parser.parse_args()
    
    # Initialize aggregator
    aggregator = FeedAggregator(args.config)
    
    # Run aggregation
    report = aggregator.aggregate()
    
    # Save JSON report
    aggregator.save_json_report(report, args.json_output)
    
    # Save/print human-readable report
    if args.text_output or args.print:
        readable = aggregator.generate_human_readable(report)
        
        if args.text_output:
            with open(args.text_output, 'w') as f:
                f.write(readable)
            print(f"Text report saved to: {args.text_output}")
        
        if args.print:
            print("\n" + readable)


if __name__ == "__main__":
    main()
