"""Import API routes for CSV and STIX 2.1 data ingestion."""

import json
import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from cti.core.database import get_db
from cti.core.dependencies import AnalystUser
from cti.schemas.import_export import (
    CSVImportResponse,
    CSVPreviewResponse,
    STIXImportResponse,
)
from cti.services import import_service, observable_service

logger = logging.getLogger(__name__)

router = APIRouter()

# Maximum upload file size (10 MB)
_MAX_FILE_SIZE = 10 * 1024 * 1024


async def _read_upload_file(file: UploadFile, max_size: int = _MAX_FILE_SIZE) -> bytes:
    """Read upload file content with size limit."""
    content = await file.read()
    if len(content) > max_size:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Maximum size is {max_size // (1024 * 1024)} MB",
        )
    return content


def _decode_file_content(content_bytes: bytes, *, allow_latin1: bool = True) -> str:
    """Decode file bytes to string, trying UTF-8 first then Latin-1."""
    try:
        return content_bytes.decode("utf-8")
    except UnicodeDecodeError:
        if allow_latin1:
            try:
                return content_bytes.decode("latin-1")
            except UnicodeDecodeError:
                pass
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not decode file. Please use UTF-8 encoding.",
        ) from None


@router.post("/csv/preview", response_model=CSVPreviewResponse)
async def preview_csv_import(
    _user: AnalystUser,
    file: UploadFile = File(...),
    column_mapping: str | None = Form(default=None),
) -> CSVPreviewResponse:
    """Upload a CSV file and preview the first 50 rows with auto-detected column mapping.

    Optionally provide a manual column_mapping as a JSON string to override detection.
    """
    content_bytes = await _read_upload_file(file)
    file_content = _decode_file_content(content_bytes)

    # Parse optional column mapping from JSON string
    mapping_override: dict[str, str] | None = None
    if column_mapping:
        try:
            mapping_override = json.loads(column_mapping)
        except json.JSONDecodeError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid column_mapping JSON",
            ) from exc

    detected_mapping, rows, total_rows, errors = import_service.preview_csv(
        file_content, column_mapping=mapping_override, limit=50
    )

    return CSVPreviewResponse(
        detected_mapping=detected_mapping,
        rows=rows,
        total_rows=total_rows,
        errors=errors,
    )


@router.post("/csv", response_model=CSVImportResponse)
async def import_csv(
    _user: AnalystUser,
    db: AsyncSession = Depends(get_db),
    file: UploadFile = File(...),
    column_mapping: str = Form(...),
) -> CSVImportResponse:
    """Import observables from a CSV file with a confirmed column mapping.

    The column_mapping must be a JSON string mapping CSV headers to observable fields.
    """
    content_bytes = await _read_upload_file(file)
    file_content = _decode_file_content(content_bytes)

    try:
        mapping = json.loads(column_mapping)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid column_mapping JSON",
        ) from exc

    if not isinstance(mapping, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="column_mapping must be a JSON object",
        )

    items, parse_errors = import_service.parse_csv(file_content, mapping)

    imported = 0
    skipped = 0
    import_errors: list[str] = list(parse_errors)

    for idx, item in enumerate(items):
        try:
            await observable_service.create_observable(db, item)
            imported += 1
        except Exception as exc:
            skipped += 1
            import_errors.append(f"Item {idx + 1} ({item.value}): {exc}")

    return CSVImportResponse(
        imported=imported,
        skipped=skipped,
        errors=import_errors,
    )


@router.post("/stix", response_model=STIXImportResponse)
async def import_stix(
    _user: AnalystUser,
    db: AsyncSession = Depends(get_db),
    file: UploadFile = File(...),
) -> STIXImportResponse:
    """Import observables from a STIX 2.1 Bundle JSON file."""
    content_bytes = await _read_upload_file(file)
    file_content = _decode_file_content(content_bytes, allow_latin1=False)

    try:
        data = json.loads(file_content)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON in STIX bundle file",
        ) from exc

    if not isinstance(data, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="STIX bundle must be a JSON object",
        )

    bundle_type = data.get("type", "")
    if bundle_type != "bundle":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Expected STIX bundle (type='bundle'), got type='{bundle_type}'",
        )

    # Use full parser to capture SDOs and relationships
    parse_result = import_service.parse_stix_bundle_full(data)

    imported = 0
    skipped = 0
    import_errors: list[str] = list(parse_result.errors)
    observable_id_map: dict[str, str] = {}  # value -> UUID (as str for mapping)

    for idx, item in enumerate(parse_result.observables):
        try:
            obs = await observable_service.create_observable(db, item)
            observable_id_map[item.value] = obs.id
            imported += 1
        except Exception as exc:
            skipped += 1
            import_errors.append(f"Item {idx + 1} ({item.value}): {exc}")

    # Process STIX correlations (threat actors, campaigns, techniques, relationships)
    correlations_created = 0
    threat_actors_resolved = 0
    campaigns_resolved = 0
    techniques_mapped = 0

    if observable_id_map:
        try:
            correlation_events = await import_service.process_stix_correlations(
                db, parse_result, observable_id_map
            )
            correlations_created = len(correlation_events)
            for evt in correlation_events:
                if evt.action_type == "link_threat_actor":
                    threat_actors_resolved += 1
                elif evt.action_type == "link_campaign":
                    campaigns_resolved += 1
                elif evt.action_type == "map_technique":
                    techniques_mapped += 1
        except Exception as exc:
            logger.error("STIX correlation processing failed: %s", exc, exc_info=True)
            import_errors.append(f"Correlation processing error: {exc}")

    return STIXImportResponse(
        imported=imported,
        skipped=skipped,
        errors=import_errors,
        correlations_created=correlations_created,
        threat_actors_resolved=threat_actors_resolved,
        campaigns_resolved=campaigns_resolved,
        techniques_mapped=techniques_mapped,
    )
