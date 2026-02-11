from cti.enrichment.abuseipdb import AbuseIPDBProvider
from cti.enrichment.base import BaseEnrichmentProvider
from cti.enrichment.greynoise import GreyNoiseProvider
from cti.enrichment.shodan import ShodanProvider
from cti.enrichment.urlscan import URLScanProvider
from cti.enrichment.virustotal import VirusTotalProvider

PROVIDER_REGISTRY: dict[str, BaseEnrichmentProvider] = {
    "virustotal": VirusTotalProvider(),
    "abuseipdb": AbuseIPDBProvider(),
    "shodan": ShodanProvider(),
    "greynoise": GreyNoiseProvider(),
    "urlscan": URLScanProvider(),
}


def get_enrichment_provider(name: str) -> BaseEnrichmentProvider | None:
    return PROVIDER_REGISTRY.get(name)
