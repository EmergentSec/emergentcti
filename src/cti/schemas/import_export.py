from pydantic import BaseModel, Field


class CSVPreviewResponse(BaseModel):
    detected_mapping: dict[str, str]
    rows: list[dict]
    total_rows: int
    errors: list[str] = Field(default_factory=list)


class CSVImportRequest(BaseModel):
    column_mapping: dict[str, str]


class CSVImportResponse(BaseModel):
    imported: int
    skipped: int
    errors: list[str] = Field(default_factory=list)


class STIXImportResponse(BaseModel):
    imported: int
    skipped: int
    errors: list[str] = Field(default_factory=list)
    correlations_created: int = 0
    threat_actors_resolved: int = 0
    campaigns_resolved: int = 0
    techniques_mapped: int = 0
