import ipaddress
import math
import re
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from cti.models.observable import ObservableType

HASH_LENGTHS = {"md5": 32, "sha1": 40, "sha256": 64, "sha512": 128}
DOMAIN_REGEX = re.compile(
    r"^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$"
)
EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
ASN_REGEX = re.compile(r"^AS\d+$", re.IGNORECASE)
URL_REGEX = re.compile(r"^https?://\S+$")

OBSERVABLE_CATEGORIES = [
    "malware", "c2", "trojan", "phishing", "ransomware", "botnet",
    "exploit", "apt", "scanner", "spam", "suspicious", "benign", "other",
]


class ObservableCreate(BaseModel):
    type: ObservableType
    value: str
    confidence_score: int = Field(default=50, ge=0, le=100)
    first_seen: datetime | None = None
    last_seen: datetime | None = None
    tlp: str = "clear"
    context: dict | None = None
    category: str | None = None
    description: str | None = None
    tags: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_value_for_type(self) -> "ObservableCreate":
        t = self.type
        v = self.value.strip()
        self.value = v

        if t == ObservableType.ip_addr:
            try:
                ipaddress.ip_address(v)
            except ValueError:
                raise ValueError(f"Invalid IP address: {v}")

        elif t == ObservableType.domain_name:
            if not DOMAIN_REGEX.match(v):
                raise ValueError(f"Invalid domain name: {v}")

        elif t == ObservableType.file_hash:
            v_lower = v.lower()
            if not re.match(r"^[a-f0-9]+$", v_lower):
                raise ValueError("File hash must be hexadecimal")
            if len(v_lower) not in HASH_LENGTHS.values():
                valid = ", ".join(f"{k}={l}" for k, l in HASH_LENGTHS.items())
                raise ValueError(f"Invalid hash length {len(v_lower)}. Valid: {valid}")
            self.value = v_lower

        elif t == ObservableType.email_addr:
            if not EMAIL_REGEX.match(v):
                raise ValueError(f"Invalid email address: {v}")

        elif t == ObservableType.cidr:
            try:
                ipaddress.ip_network(v, strict=False)
            except ValueError:
                raise ValueError(f"Invalid CIDR notation: {v}")

        elif t == ObservableType.asn:
            if not ASN_REGEX.match(v):
                raise ValueError(f"Invalid ASN format (expected AS\\d+): {v}")

        elif t == ObservableType.url:
            if not URL_REGEX.match(v):
                raise ValueError(f"Invalid URL: {v}")

        return self


class ObservableUpdate(BaseModel):
    confidence_score: int | None = Field(default=None, ge=0, le=100)
    tlp: str | None = None
    context: dict | None = None
    category: str | None = None
    description: str | None = None
    tags: list[str] | None = None


class TagResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    color: str


class FeedSourceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str


class ObservableResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    type: ObservableType
    value: str
    confidence_score: int
    first_seen: datetime | None
    last_seen: datetime | None
    tlp: str
    context: dict | None
    category: str | None
    description: str | None
    external_references: list[dict] | None
    expires_at: datetime | None = None
    is_active: bool = True
    tags: list[str]
    sources: list[FeedSourceResponse]
    created_at: datetime
    updated_at: datetime

    @field_validator("tags", mode="before")
    @classmethod
    def flatten_tags(cls, v: Any) -> list[str]:
        if not v:
            return []
        result: list[str] = []
        for item in v:
            if isinstance(item, str):
                result.append(item)
            elif hasattr(item, "name"):
                result.append(item.name)
            elif isinstance(item, dict):
                result.append(item.get("name", ""))
            else:
                result.append(str(item))
        return result


class ObservableListResponse(BaseModel):
    items: list[ObservableResponse]
    total: int
    page: int
    size: int
    pages: int = 0

    @model_validator(mode="after")
    def compute_pages(self) -> "ObservableListResponse":
        if self.size > 0:
            self.pages = math.ceil(self.total / self.size)
        return self


class ObservableStatsResponse(BaseModel):
    total: int
    by_type: dict[str, int]
