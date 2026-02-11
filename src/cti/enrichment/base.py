from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import ClassVar


@dataclass
class EnrichmentResult:
    provider: str
    success: bool
    data: dict = field(default_factory=dict)
    error: str | None = None
    summary: str | None = None  # Human-readable summary


class BaseEnrichmentProvider(ABC):
    name: ClassVar[str]
    supported_types: ClassVar[list[str]]  # Observable types this provider supports

    @abstractmethod
    async def enrich(
        self, observable_type: str, observable_value: str, api_key: str
    ) -> EnrichmentResult:
        """Run enrichment and return result."""
        ...

    def supports_type(self, observable_type: str) -> bool:
        return observable_type in self.supported_types
