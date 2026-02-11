import logging
from typing import ClassVar

import httpx

from cti.enrichment.base import BaseEnrichmentProvider, EnrichmentResult

logger = logging.getLogger(__name__)

SHODAN_BASE_URL = "https://api.shodan.io"


class ShodanProvider(BaseEnrichmentProvider):
    name: ClassVar[str] = "shodan"
    supported_types: ClassVar[list[str]] = ["ip-addr"]

    async def enrich(
        self, observable_type: str, observable_value: str, api_key: str
    ) -> EnrichmentResult:
        params = {"key": api_key}

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(
                    f"{SHODAN_BASE_URL}/shodan/host/{observable_value}",
                    params=params,
                )

                if resp.status_code == 404:
                    return EnrichmentResult(
                        provider=self.name,
                        success=True,
                        data={"found": False},
                        summary="Shodan: No data available",
                    )

                resp.raise_for_status()
                body = resp.json()

                ports = body.get("ports", [])
                os_name = body.get("os", None)
                org = body.get("org", "N/A")
                country = body.get("country_code", "N/A")
                vulns = body.get("vulns", [])
                hostnames = body.get("hostnames", [])
                asn = body.get("asn", None)

                result_data = {
                    "found": True,
                    "ports": ports,
                    "os": os_name,
                    "org": org,
                    "country_code": country,
                    "vulns": vulns,
                    "hostnames": hostnames,
                    "asn": asn,
                }

                summary_parts = [f"Shodan: {len(ports)} open ports"]
                if org != "N/A":
                    summary_parts.append(f"org: {org}")
                if vulns:
                    summary_parts.append(f"{len(vulns)} vulns")

                return EnrichmentResult(
                    provider=self.name,
                    success=True,
                    data=result_data,
                    summary=", ".join(summary_parts),
                )

        except httpx.HTTPStatusError as e:
            logger.error("Shodan API error: %s", e)
            return EnrichmentResult(
                provider=self.name,
                success=False,
                error=f"HTTP {e.response.status_code}: {e.response.text[:200]}",
            )
        except Exception as e:
            logger.error("Shodan enrichment failed: %s", e)
            return EnrichmentResult(
                provider=self.name,
                success=False,
                error=str(e),
            )
