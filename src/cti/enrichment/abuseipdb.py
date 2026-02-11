import logging
from typing import ClassVar

import httpx

from cti.enrichment.base import BaseEnrichmentProvider, EnrichmentResult

logger = logging.getLogger(__name__)

ABUSEIPDB_BASE_URL = "https://api.abuseipdb.com/api/v2"


class AbuseIPDBProvider(BaseEnrichmentProvider):
    name: ClassVar[str] = "abuseipdb"
    supported_types: ClassVar[list[str]] = ["ip-addr"]

    async def enrich(
        self, observable_type: str, observable_value: str, api_key: str
    ) -> EnrichmentResult:
        headers = {
            "Key": api_key,
            "Accept": "application/json",
        }
        params = {
            "ipAddress": observable_value,
            "maxAgeInDays": "90",
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(
                    f"{ABUSEIPDB_BASE_URL}/check",
                    headers=headers,
                    params=params,
                )
                resp.raise_for_status()
                body = resp.json()
                data = body.get("data", {})

                confidence = data.get("abuseConfidenceScore", 0)
                total_reports = data.get("totalReports", 0)
                country = data.get("countryCode", "N/A")
                isp = data.get("isp", "N/A")
                is_public = data.get("isPublic", True)
                usage_type = data.get("usageType", "N/A")

                result_data = {
                    "abuseConfidenceScore": confidence,
                    "totalReports": total_reports,
                    "countryCode": country,
                    "isp": isp,
                    "isPublic": is_public,
                    "usageType": usage_type,
                }

                summary = (
                    f"AbuseIPDB: {confidence}% confidence, "
                    f"{total_reports} reports"
                )

                return EnrichmentResult(
                    provider=self.name,
                    success=True,
                    data=result_data,
                    summary=summary,
                )

        except httpx.HTTPStatusError as e:
            logger.error("AbuseIPDB API error: %s", e)
            return EnrichmentResult(
                provider=self.name,
                success=False,
                error=f"HTTP {e.response.status_code}: {e.response.text[:200]}",
            )
        except Exception as e:
            logger.error("AbuseIPDB enrichment failed: %s", e)
            return EnrichmentResult(
                provider=self.name,
                success=False,
                error=str(e),
            )
