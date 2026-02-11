import math
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from cti.models.correlation import CorrelationActionType

# ---------------------------------------------------------------------------
# Correlation Rule schemas
# ---------------------------------------------------------------------------

_ACTION_TARGET_MAP: dict[str, str] = {
    CorrelationActionType.link_threat_actor: "target_threat_actor_id",
    CorrelationActionType.link_campaign: "target_campaign_id",
    CorrelationActionType.map_technique: "target_technique_id",
}

_ALL_TARGET_FIELDS = set(_ACTION_TARGET_MAP.values())


class CorrelationRuleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=256)
    enabled: bool = True
    match_type: str | None = None
    match_value_pattern: str | None = None
    match_tags: list[str] | None = None
    match_tlp: str | None = None
    match_confidence_min: int | None = Field(default=None, ge=0, le=100)
    match_feed_id: uuid.UUID | None = None
    action_type: CorrelationActionType
    target_threat_actor_id: uuid.UUID | None = None
    target_campaign_id: uuid.UUID | None = None
    target_technique_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def validate_target(self) -> "CorrelationRuleCreate":
        required_field = _ACTION_TARGET_MAP[self.action_type]
        required_value = getattr(self, required_field)
        if required_value is None:
            raise ValueError(
                f"action_type '{self.action_type}' requires {required_field} to be set"
            )
        # Ensure the other target fields are not set
        for field_name in _ALL_TARGET_FIELDS:
            if field_name != required_field and getattr(self, field_name) is not None:
                raise ValueError(
                    f"action_type '{self.action_type}' must not set {field_name}"
                )
        return self


class CorrelationRuleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=256)
    enabled: bool | None = None
    match_type: str | None = None
    match_value_pattern: str | None = None
    match_tags: list[str] | None = None
    match_tlp: str | None = None
    match_confidence_min: int | None = Field(default=None, ge=0, le=100)
    match_feed_id: uuid.UUID | None = None
    action_type: CorrelationActionType | None = None
    target_threat_actor_id: uuid.UUID | None = None
    target_campaign_id: uuid.UUID | None = None
    target_technique_id: uuid.UUID | None = None


class CorrelationRuleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    enabled: bool
    created_by: uuid.UUID | None
    match_type: str | None
    match_value_pattern: str | None
    match_tags: list[str] | None
    match_tlp: str | None
    match_confidence_min: int | None
    match_feed_id: uuid.UUID | None
    action_type: str
    target_threat_actor_id: uuid.UUID | None
    target_campaign_id: uuid.UUID | None
    target_technique_id: uuid.UUID | None
    target_name: str | None = None
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Correlation Event schemas
# ---------------------------------------------------------------------------


class CorrelationEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    rule_id: uuid.UUID | None
    observable_id: uuid.UUID
    action_type: str
    target_id: uuid.UUID
    correlated_at: datetime
    source: str
    rule_name: str | None = None
    observable_value: str | None = None


class CorrelationEventListResponse(BaseModel):
    items: list[CorrelationEventResponse]
    total: int
    page: int
    size: int
    pages: int = 0

    @model_validator(mode="after")
    def compute_pages(self) -> "CorrelationEventListResponse":
        if self.size > 0:
            self.pages = math.ceil(self.total / self.size)
        return self
