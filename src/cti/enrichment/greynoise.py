import logging
from typing import ClassVar

import httpx

from cti.enrichment.base import BaseEnrichmentProvider, EnrichmentResult

logger = logging.getLogger(__name__)

GREYNOISE_BASE_URL = "https://api.greynoise.io/v3/community"


class GreyNoiseProvider(BaseEnrichmentProvider):
    name: ClassVar[str] = "greynoise"
    supported_types: ClassVar[list[str]] = ["ip-addr"]

    async def enrich(
        self, observable_type: str, observable_value: str, api_key: str
    ) -> EnrichmentResult:
        headers = {
            "key": api_key,
            "Accept": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(
                    f"{GREYNOISE_BASE_URL}/{observable_value}",
                    headers=headers,
                )

                if resp.status_code == 404:
                    return EnrichmentResult(
                        provider=self.name,
                        success=True,
                        data={"found": False},
                        summary="GreyNoise: IP not observed",
                    )

                resp.raise_for_status()
                body = resp.json()

                noise = body.get("noise", False)
                riot = body.get("riot", False)
                classification = body.get("classification", "unknown")
                name = body.get("name", "N/A")
                last_seen = body.get("last_seen", None)
                message = body.get("message", "")

                result_data = {
                    "noise": noise,
                    "riot": riot,
                    "classification": classification,
                    "name": name,
                    "last_seen": last_seen,
                    "message": message,
                }

                summary = (
                    f"GreyNoise: {classification}, "
                    f"riot={riot}"
                )
                if name != "N/A":
                    summary += f", name={name}"

                return EnrichmentResult(
                    provider=self.name,
                    success=True,
                    data=result_data,
                    summary=summary,
                )

        except httpx.HTTPStatusError as e:
            logger.error("GreyNoise API error: %s", e)
            return EnrichmentResult(
                provider=self.name,
                success=False,
                error=f"HTTP {e.response.status_code}: {e.response.text[:200]}",
            )
        except Exception as e:
            logger.error("GreyNoise enrichment failed: %s", e)
            return EnrichmentResult(
                provider=self.name,
                success=False,
                error=str(e),
            )
