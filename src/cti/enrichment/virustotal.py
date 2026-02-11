import base64
import logging
from typing import ClassVar

import httpx

from cti.enrichment.base import BaseEnrichmentProvider, EnrichmentResult

logger = logging.getLogger(__name__)

VT_BASE_URL = "https://www.virustotal.com/api/v3"


class VirusTotalProvider(BaseEnrichmentProvider):
    name: ClassVar[str] = "virustotal"
    supported_types: ClassVar[list[str]] = [
        "ip-addr", "domain-name", "url", "file-hash",
    ]

    async def enrich(
        self, observable_type: str, observable_value: str, api_key: str
    ) -> EnrichmentResult:
        headers = {"x-apikey": api_key}

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                if observable_type == "ip-addr":
                    url = f"{VT_BASE_URL}/ip_addresses/{observable_value}"
                    resp = await client.get(url, headers=headers)

                elif observable_type == "domain-name":
                    url = f"{VT_BASE_URL}/domains/{observable_value}"
                    resp = await client.get(url, headers=headers)

                elif observable_type == "url":
                    # VT requires URL-safe base64 encoded URL as identifier
                    url_id = (
                        base64.urlsafe_b64encode(
                            observable_value.encode()
                        )
                        .decode()
                        .rstrip("=")
                    )
                    url = f"{VT_BASE_URL}/urls/{url_id}"
                    resp = await client.get(url, headers=headers)

                elif observable_type == "file-hash":
                    url = f"{VT_BASE_URL}/files/{observable_value}"
                    resp = await client.get(url, headers=headers)

                else:
                    return EnrichmentResult(
                        provider=self.name,
                        success=False,
                        error=f"Unsupported observable type: {observable_type}",
                    )

                if resp.status_code == 404:
                    return EnrichmentResult(
                        provider=self.name,
                        success=True,
                        data={"found": False},
                        summary="VT: Not found in database",
                    )

                resp.raise_for_status()
                body = resp.json()
                attributes = body.get("data", {}).get("attributes", {})

                stats = attributes.get("last_analysis_stats", {})
                malicious = stats.get("malicious", 0)
                total = sum(stats.values()) if stats else 0
                reputation = attributes.get("reputation", "N/A")
                tags = attributes.get("tags", [])

                result_data = {
                    "found": True,
                    "last_analysis_stats": stats,
                    "reputation": reputation,
                    "tags": tags,
                }

                summary = f"VT: {malicious}/{total} malicious"
                if reputation != "N/A":
                    summary += f", reputation={reputation}"

                return EnrichmentResult(
                    provider=self.name,
                    success=True,
                    data=result_data,
                    summary=summary,
                )

        except httpx.HTTPStatusError as e:
            logger.error("VirusTotal API error: %s", e)
            return EnrichmentResult(
                provider=self.name,
                success=False,
                error=f"HTTP {e.response.status_code}: {e.response.text[:200]}",
            )
        except Exception as e:
            logger.error("VirusTotal enrichment failed: %s", e)
            return EnrichmentResult(
                provider=self.name,
                success=False,
                error=str(e),
            )
