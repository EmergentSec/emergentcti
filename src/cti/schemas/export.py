from datetime import datetime
from pydantic import BaseModel
from cti.models.observable import ObservableType


class ExportObservable(BaseModel):
    type: ObservableType
    value: str
    confidence_score: int
    last_seen: datetime | None
    sources: list[str]  # Feed names


class JsonExportResponse(BaseModel):
    exported_at: datetime
    count: int
    filters: dict
    observables: list[ExportObservable]
