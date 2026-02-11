import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, model_validator

from cti.enrichment.registry import PROVIDER_REGISTRY


class EnrichmentConfigResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    provider_name: str
    enabled: bool
    auto_enrich: bool
    has_api_key: bool = False
    config: dict
    priority: int
    supported_types: list[str] = []
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="before")
    @classmethod
    def compute_fields(cls, data: Any) -> Any:
        # Handle both ORM objects and dicts
        if hasattr(data, "__dict__"):
            # ORM model instance
            provider_name = data.provider_name
            api_key_encrypted = data.api_key_encrypted
            result = {
                "id": data.id,
                "provider_name": provider_name,
                "enabled": data.enabled,
                "auto_enrich": data.auto_enrich,
                "has_api_key": api_key_encrypted is not None,
                "config": data.config,
                "priority": data.priority,
                "created_at": data.created_at,
                "updated_at": data.updated_at,
            }
        else:
            # dict
            provider_name = data.get("provider_name", "")
            result = dict(data)
            result["has_api_key"] = data.get("api_key_encrypted") is not None

        # Look up supported types from provider registry
        provider = PROVIDER_REGISTRY.get(provider_name)
        result["supported_types"] = (
            provider.supported_types if provider else []
        )
        return result


class EnrichmentConfigUpdate(BaseModel):
    enabled: bool | None = None
    auto_enrich: bool | None = None
    api_key: str | None = None  # plaintext, will be encrypted
    config: dict | None = None
    priority: int | None = None


class EnrichmentRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    observable_id: uuid.UUID
    provider_name: str
    status: str
    result_data: dict | None
    summary: str | None
    error_message: str | None
    started_at: datetime | None
    completed_at: datetime | None
    triggered_by: uuid.UUID | None
    created_at: datetime


class EnrichmentTriggerRequest(BaseModel):
    provider_name: str | None = None  # None = all enabled providers


class ProviderInfo(BaseModel):
    name: str
    supported_types: list[str]
    configured: bool
    enabled: bool
