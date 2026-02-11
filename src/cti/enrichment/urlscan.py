import asyncio
import logging
from typing import ClassVar

import httpx

from cti.enrichment.base import BaseEnrichmentProvider, EnrichmentResult

logger = logging.getLogger(__name__)

URLSCAN_BASE_URL = "https://urlscan.io/api/v1"
URLSCAN_POLL_INTERVAL = 5  # seconds between polling attempts
URLSCAN_MAX_POLLS = 12  # max polls (~60 seconds total)


class URLScanProvider(BaseEnrichmentProvider):
    name: ClassVar[str] = "urlscan"
    supported_types: ClassVar[list[str]] = ["url", "domain-name"]

    async def enrich(
        self, observable_type: str, observable_value: str, api_key: str
    ) -> EnrichmentResult:
        headers = {
            "API-Key": api_key,
            "Content-Type": "application/json",
        }

        # For domain-name, construct a URL to scan
        scan_url = observable_value
        if observable_type == "domain-name":
            scan_url = f"https://{observable_value}"

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # Submit scan
                submit_resp = await client.post(
                    f"{URLSCAN_BASE_URL}/scan/",
                    headers=headers,
                    json={"url": scan_url, "visibility": "unlisted"},
                )

                if submit_resp.status_code == 429:
                    return EnrichmentResult(
                        provider=self.name,
                        success=False,
                        error="Rate limit exceeded",
                    )

                submit_resp.raise_for_status()
                submit_data = submit_resp.json()
                scan_uuid = submit_data.get("uuid")

                if not scan_uuid:
                    return EnrichmentResult(
                        provider=self.name,
                        success=False,
                        error="No scan UUID returned",
                    )

                # Poll for result
                result_url = f"{URLSCAN_BASE_URL}/result/{scan_uuid}/"
                for _ in range(URLSCAN_MAX_POLLS):
                    await asyncio.sleep(URLSCAN_POLL_INTERVAL)
                    result_resp = await client.get(result_url)

                    if result_resp.status_code == 200:
                        body = result_resp.json()
                        verdicts = body.get("verdicts", {})
                        overall = verdicts.get("overall", {})
                        page = body.get("page", {})

                        malicious = overall.get("malicious", False)
                        score = overall.get("score", 0)
                        domain = page.get("domain", "N/A")
                        country = page.get("country", "N/A")
                        server = page.get("server", "N/A")
                        lists = body.get("lists", {})

                        result_data = {
                            "scan_uuid": scan_uuid,
                            "malicious": malicious,
                            "score": score,
                            "domain": domain,
                            "country": country,
                            "server": server,
                            "ips": lists.get("ips", []),
                            "urls": lists.get("urls", [])[:20],
                        }

                        summary = (
                            f"URLScan: malicious={malicious}, "
                            f"score={score}"
                        )

                        return EnrichmentResult(
                            provider=self.name,
                            success=True,
                            data=result_data,
                            summary=summary,
                        )

                    if result_resp.status_code != 404:
                        # 404 means still processing, anything else is an error
                        result_resp.raise_for_status()

                # Timed out waiting for results
                return EnrichmentResult(
                    provider=self.name,
                    success=True,
                    data={
                        "scan_uuid": scan_uuid,
                        "status": "pending",
                    },
                    summary="URLScan: scan submitted, results pending",
                )

        except httpx.HTTPStatusError as e:
            logger.error("URLScan API error: %s", e)
            return EnrichmentResult(
                provider=self.name,
                success=False,
                error=f"HTTP {e.response.status_code}: {e.response.text[:200]}",
            )
        except Exception as e:
            logger.error("URLScan enrichment failed: %s", e)
            return EnrichmentResult(
                provider=self.name,
                success=False,
                error=str(e),
            )
